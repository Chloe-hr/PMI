"""Tests for the Stage 4.0A evaluation report (run after build_stage4_0a_report.py).

    .venv/Scripts/python.exe -m unittest research/evaluation/stage4_0a/test_stage4_0a_report.py -v
"""
from __future__ import annotations

import importlib.util
import re
import unittest
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
CSV = HERE / "csv"
spec = importlib.util.spec_from_file_location("s40a", HERE / "build_stage4_0a_report.py")
s40a = importlib.util.module_from_spec(spec)
spec.loader.exec_module(s40a)


class Outputs(unittest.TestCase):
    def test_reports_exist(self):
        for name in ("stage4_0a_evaluation_report.html", "stage4_0a_evaluation_report.md"):
            self.assertGreater((HERE / name).stat().st_size, 10_000, name)

    def test_every_experiment_has_all_required_subsections(self):
        md = (HERE / "stage4_0a_evaluation_report.md").read_text(encoding="utf-8")
        required = ["Research objective", "Dataset and features", "Model architecture", "Training and validation methodology",
                    "Hyperparameters", "Maximum and executed epochs", "Best checkpoint and stopping criterion",
                    "Performance metrics", "Convergence, overfitting or underfitting", "Research limitations",
                    "Reason for moving to the next experiment"]
        sections = re.split(r"\n## (?=E\d )", md)[1:]
        self.assertEqual([s[:2] for s in sections], [f"E{i}" for i in range(1, 9)])
        for s in sections:
            for r in required:
                self.assertIn(r, s.split("\n## ")[0], f"{s[:2]} missing {r}")

    def test_figures_and_architecture_exist(self):
        for f in ("E1_loss_curve", "E3_loss_curves", "E3_fold_mae", "E4_oof_evidence", "E5_oof_evidence", "E6_oof_evidence",
                  "E7_dev_folds", "E8_loss_curves", "E8_comparison", "E8_seed_spread", "chronology"):
            self.assertTrue((HERE / "figures" / f"{f}.png").is_file(), f)
        for a in ("A1_mendeley_mlp", "A2_duration_gnn", "A3_cambridge_classical", "A4_cambridge_sage"):
            self.assertIn("<svg", (HERE / "figures/architecture" / f"{a}.svg").read_text(encoding="utf-8"))

    def test_html_self_contained_and_interactive(self):
        page = (HERE / "stage4_0a_evaluation_report.html").read_text(encoding="utf-8")
        self.assertNotRegex(page, r'<script[^>]+src=')
        self.assertNotRegex(page, r'<img[^>]+src="(?!data:)')
        for eid in ("E1", "E3", "E8"):
            self.assertIn(f'data-exp="{eid}"', page)


class Separation(unittest.TestCase):
    def test_scaled_mse_histories_attributed_to_mendeley_only(self):
        reg = pd.read_csv(CSV / "loss_history_registry.csv")
        mse = reg[reg["columns"] == "epoch|train_mse_scaled|validation_mse_scaled"]
        self.assertEqual(set(mse.experiment), {"E1", "E2", "E3"})
        self.assertEqual(len(mse), 1 + 5 + 15)
        l1 = reg[reg["columns"].str.contains("train_l1_log")]
        self.assertEqual(set(l1.experiment), {"E8"})

    def test_e2_is_byte_identical_to_e3_repeat1(self):
        ident = pd.read_csv(CSV / "E2_vs_E3_repeat1_identity.csv")
        self.assertTrue(ident.identical.all())

    def test_same_size_checkpoints_have_distinct_hashes(self):
        ck = pd.read_csv(CSV / "checkpoint_inventory.csv")
        g = ck[ck.path.str.match(r"models/gnn_(synthetic|dslib|dslib_filtered)/model.pt")]
        self.assertEqual(len(g), 3)
        self.assertEqual(g.bytes.nunique(), 1)
        self.assertEqual(g.sha256.nunique(), 3)

    def test_no_combined_cross_experiment_ranking_file(self):
        for p in CSV.glob("*.csv"):
            df = pd.read_csv(p, nrows=200)
            if "experiment" in df.columns and any(c in df.columns for c in ("MAE", "MAE_days", "mean_block_mae_days")):
                self.assertEqual(df.experiment.nunique(), 1, f"{p.name} mixes experiments in one metric table")

    def test_heldout_aggregate_is_flagged(self):
        h = pd.read_csv(CSV / "metrics_E7_HISTORICAL_heldout_aggregate.csv")
        self.assertTrue(h.WARNING.str.contains("locked").all())


class LockedTestGuard(unittest.TestCase):
    def test_guard_refuses_locked_files(self):
        for p in sorted(s40a.LOCKED_TEST_DENYLIST) + [f"{s40a.STAGE2}/figures/mae_comparison.png"]:
            with self.assertRaises(PermissionError):
                s40a.guard(p)

    def test_generator_never_read_locked_files(self):
        read = set(pd.read_csv(CSV / "files_read.csv").file_read_by_generator)
        self.assertFalse(read & s40a.LOCKED_TEST_DENYLIST)
        self.assertFalse([r for r in read if r.startswith(s40a.LOCKED_TEST_DENY_PREFIXES)])

    def test_e8_oof_is_development_only(self):
        oof = pd.read_csv(ROOT / "models/gnn_cambridge/oof_predictions.csv", usecols=["conservative_block_id"])
        self.assertEqual(len(oof), 144_110)
        self.assertEqual(oof.conservative_block_id.nunique(), 70)


class Reproduction(unittest.TestCase):
    def test_stored_gnn_metrics_reproduce_from_oof(self):
        for eid in ("E4", "E5", "E6"):
            df = pd.read_csv(CSV / f"metrics_{eid}_oof_stored_vs_recomputed.csv")
            self.assertTrue(df.matches_to_stored_precision.all(), eid)

    def test_e8_metrics_reproduce_from_oof(self):
        self.assertTrue(pd.read_csv(CSV / "metrics_E8_stored_vs_recomputed.csv").match.all())

    def test_e3_patience_rule(self):
        c = pd.read_csv(CSV / "convergence_diagnostics.csv")
        e3 = c[c.experiment == "E3"]
        self.assertEqual(len(e3), 15)
        self.assertTrue(((e3.epochs_run - e3.best_epoch) == 150).all())

    def test_e8_runs_complete(self):
        c = pd.read_csv(CSV / "convergence_diagnostics.csv")
        e8 = c[c.experiment == "E8"]
        self.assertEqual(len(e8), 30)
        self.assertTrue(((e8.epochs_run - e8.best_epoch) == 15).all())


class Preservation(unittest.TestCase):
    def test_all_checks_pass(self):
        p = pd.read_csv(CSV / "preservation_verification.csv")
        self.assertFalse((p.status == "FAIL").any(), p[p.status == "FAIL"].path.tolist())
        self.assertGreaterEqual((p.check == "before_vs_after_stage4_0a").sum(), 342)

    def test_protected_files_unchanged_now(self):
        base = (HERE / "preservation/baseline_sha256_before_stage4_0a.txt").read_text(encoding="utf-8").splitlines()
        for line in base:
            h, path = line.split(" ", 1)
            self.assertEqual(s40a.sha256(ROOT / path.lstrip("*").strip()), h, path)


if __name__ == "__main__":
    unittest.main()
