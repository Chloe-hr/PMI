"""Safety checks for the Stage 2.3E training entry point."""
import sys
import unittest
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "training"))
from train_cambridge_experiment import FEATURES, load_frozen_data, metric_row, preprocessor  # noqa: E402


class CambridgeTrainingSafetyTests(unittest.TestCase):
    def test_feature_allowlist_is_exact(self):
        self.assertEqual(FEATURES, ["activity_description", "project_type", "uk_region"])

    def test_frozen_keys_targets_groups_and_manifest_are_valid(self):
        data, y = load_frozen_data()
        self.assertEqual(len(data), 180137)
        self.assertEqual(data.composite_activity_key.nunique(), len(data))
        self.assertTrue((y > 0).all())
        self.assertEqual(set(data.split), {"train", "test"})
        self.assertEqual(data.groupby("conservative_block_id").split.nunique().max(), 1)
        dominant = data[data.conservative_block_id == "C-5f73906a8795"]
        self.assertEqual(set(dominant.split), {"train"})

    def test_metric_is_deterministic_and_activity_weighted(self):
        a = metric_row("m", [1, 3, 10], [2, 5, 8], ["a", "a", "b"])
        b = metric_row("m", [1, 3, 10], [2, 5, 8], ["a", "a", "b"])
        self.assertEqual(a, b)
        self.assertAlmostEqual(a["mae_days"], 5 / 3)
        self.assertEqual(a["activity_weighted_mae_days"], a["mae_days"])

    def test_preprocessor_learns_vocabulary_only_from_fit_rows(self):
        train = [
            dict(activity_description="common phrase", project_type="type_a", uk_region="north"),
            dict(activity_description="common phrase", project_type="type_a", uk_region="north"),
            dict(activity_description="different wording", project_type="type_b", uk_region="west"),
        ]
        evaluation = [dict(activity_description="evaluationonlytoken", project_type="unseen_type", uk_region="south")]
        transformer = preprocessor()
        # ColumnTransformer expects a 2D tabular input; production passes a DataFrame.
        train_frame = pd.DataFrame(train)
        evaluation_frame = pd.DataFrame(evaluation)
        transformer.fit_transform(train_frame)
        vocab = transformer.named_transformers_["text"].vocabulary_
        self.assertIn("common", vocab)
        self.assertNotIn("evaluationonlytoken", vocab)
        # Unknown context categories transform without refitting the encoder.
        self.assertEqual(transformer.transform(evaluation_frame).shape[0], 1)

    def test_fold_row_construction_does_not_duplicate_model_key(self):
        # Regression: main() once passed model= twice and crashed on the first fold.
        row = dict(fold=0, **metric_row("ridge", [1, 2], [1, 3], ["g", "g"]))
        self.assertEqual((row["fold"], row["model"]), (0, "ridge"))

    def test_preflight_refuses_second_heldout_evaluation_and_reports_missing_inputs(self):
        import tempfile
        import train_cambridge_experiment as m
        saved = (m.OUT, m.RAW_JSON)
        try:
            with tempfile.TemporaryDirectory() as folder:
                m.OUT = Path(folder)
                (m.OUT / "heldout_predictions.csv").write_text("already evaluated\n")
                m.RAW_JSON = Path(folder) / "absent.json"
                with self.assertRaises(SystemExit) as ctx:
                    m.preflight()
                message = str(ctx.exception)
                self.assertIn("held-out results already exist", message)
                self.assertIn("missing", message)
                self.assertIn("nothing was fitted", message)
        finally:
            m.OUT, m.RAW_JSON = saved


if __name__ == "__main__":
    unittest.main()
