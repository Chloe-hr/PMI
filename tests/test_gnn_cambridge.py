"""Stage 3.7 Cambridge GNN: graph integrity, labels, missing features and leakage.

    python -m unittest tests.test_gnn_cambridge

Synthetic tests always run. Cache tests run when data/processed/gnn_cambridge exists
(python research/gnn/cambridge_graph.py) and the frozen Stage 2.3D artifacts are present.
"""
import json
import sys
import unittest
from pathlib import Path

import numpy as np
import pandas as pd
import torch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "research" / "gnn"))
import cambridge_graph as cg  # noqa: E402
from cambridge_model import CambridgeSAGE  # noqa: E402
from train_cambridge import inner_stop_blocks  # noqa: E402

CACHE = ROOT / "data/processed/gnn_cambridge"
FORBIDDEN = ("date", "actual", "planned", "progress", "percent", "float", "duration", "growth", "lag", "gmm",
             "weather", "target", "days")


class StubFeaturizer:
    def transform(self, df):
        return np.stack([df.activity_description.str.len().to_numpy(), np.ones(len(df))], 1).astype(np.float32)


def toy():
    nodes = pd.DataFrame({
        "project_key": ["P", "P", "P", "Q"], "activity_key": ["a", "b", "c", "a"],
        "conservative_block_id": ["B1", "B1", "B1", "B2"], "development_validation_fold": ["0", "0", "0", "1"],
        "activity_description": ["dig", "pour slab", "", "fit out"], "project_type": ["Rail"] * 4,
        "uk_region": ["Midlands"] * 4, "labelled": [True, True, False, True]})
    edges = pd.DataFrame({"project_key": ["P", "P"], "predecessor_key": ["a", "b"], "successor_key": ["b", "c"],
                          "relationship_type": ["PR_FS", "PR_SS"]})
    dev = pd.DataFrame({"project_key": ["P", "P", "Q"], "activity_key": ["a", "b", "a"], cg.TARGET: [2.0, 10.0, 0.5]})
    return nodes, edges, dev


class SyntheticGraphTests(unittest.TestCase):
    def test_one_graph_per_project_and_edge_mapping(self):
        gs = cg.build_graphs(*toy(), StubFeaturizer())
        self.assertEqual([g.project_key for g in gs], ["P", "Q"])
        p = gs[0]
        self.assertEqual(p.edge_index.tolist(), [[0, 1], [1, 2]])        # a->b, b->c
        self.assertEqual(gs[1].edge_index.shape, (2, 0))

    def test_labels_are_log1p_days_only_on_labelled_nodes(self):
        p = cg.build_graphs(*toy(), StubFeaturizer())[0]
        self.assertTrue(np.allclose(p.y[:2].numpy(), np.log1p([2.0, 10.0])))
        self.assertTrue(torch.isnan(p.y[2]))

    def test_features_do_not_depend_on_labels(self):
        nodes, edges, dev = toy()
        a = cg.build_graphs(nodes, edges, dev, StubFeaturizer())[0].x
        dev[cg.TARGET] = dev[cg.TARGET] * 100
        b = cg.build_graphs(nodes, edges, dev, StubFeaturizer())[0].x
        self.assertTrue(torch.equal(a, b))

    def test_no_graph_control_ignores_edges_and_graphsage_uses_them(self):
        torch.manual_seed(0)
        x = torch.randn(5, 4)
        e = torch.tensor([[0, 1, 2], [1, 2, 3]])
        for use_graph, should_change in ((False, False), (True, True)):
            m = CambridgeSAGE(4, hidden=8, layers=2, dropout=0.0, use_graph=use_graph).eval()
            changed = not torch.allclose(m(x, e), m(x, e.new_zeros((2, 0))))
            self.assertEqual(changed, should_change)

    def test_arms_have_identical_parameter_counts(self):
        n = lambda m: sum(p.numel() for p in m.parameters())  # noqa: E731
        self.assertEqual(n(CambridgeSAGE(10, use_graph=True)), n(CambridgeSAGE(10, use_graph=False)))

    def test_inner_stopping_blocks_are_deterministic_training_blocks(self):
        blocks = [f"C-{i:03d}" for i in range(69)]
        s = inner_stop_blocks(blocks)
        self.assertEqual(s, inner_stop_blocks(list(reversed(blocks))))
        self.assertEqual(len(s), 6)
        self.assertTrue(s <= set(blocks))

    def test_outcome_phrase_rule_matches_stage_2_3c(self):
        self.assertTrue(cg.OUTCOME_TEXT.search("Completed on 3 May"))
        self.assertFalse(cg.OUTCOME_TEXT.search("complete drainage"))


@unittest.skipUnless((CACHE / "graph_manifest.json").exists(), "graph cache not built")
class CacheTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.nodes, cls.edges, cls.dev = cg.load_cached()
        cls.labels = cg.load_labels()

    def test_no_locked_test_project_or_block_in_cache(self):
        test = self.labels[self.labels.split == "test"]
        self.assertFalse(set(self.nodes.project_key) & set(test.project_key))
        self.assertFalse(set(self.nodes.conservative_block_id) & set(test.conservative_block_id))
        self.assertFalse(set(self.edges.project_key) & set(test.project_key))
        self.assertEqual(json.loads((CACHE / "graph_manifest.json").read_text())["test_projects_materialised"], 0)

    def test_every_development_row_is_exactly_one_labelled_node(self):
        lab = self.nodes[self.nodes.labelled]
        self.assertEqual(len(lab), cg.DEV_ROWS)
        self.assertFalse(self.nodes.duplicated(["project_key", "activity_key"]).any())
        self.assertEqual(set(zip(lab.project_key, lab.activity_key)), set(zip(self.dev.project_key, self.dev.activity_key)))
        self.assertEqual(lab.conservative_block_id.nunique(), cg.DEV_BLOCKS)

    def test_edges_are_intra_project_without_self_loops_or_duplicates(self):
        keys = set(zip(self.nodes.project_key, self.nodes.activity_key))
        e = self.edges
        self.assertTrue(all((p, a) in keys for p, a in zip(e.project_key, e.predecessor_key)))
        self.assertTrue(all((p, a) in keys for p, a in zip(e.project_key, e.successor_key)))
        self.assertFalse((e.predecessor_key == e.successor_key).any())
        self.assertFalse(e.duplicated(["project_key", "predecessor_key", "successor_key"]).any())

    def test_labels_valid(self):
        y = self.dev[cg.TARGET].astype(float)
        self.assertTrue(np.isfinite(y).all() and (y > 0).all())
        self.assertTrue((self.dev.verified_ground_truth.str.lower() == "false").all())

    def test_no_missing_context_features(self):
        self.assertFalse((self.nodes.project_type == "").any())
        self.assertFalse((self.nodes.uk_region == "").any())
        self.assertFalse((self.nodes[self.nodes.labelled].activity_description.str.strip() == "").any())
        self.assertFalse(self.nodes[self.nodes.labelled].description_masked.eq("True").any())

    def test_cache_columns_carry_no_post_execution_fields(self):
        cols = [c.lower() for c in list(self.nodes.columns) + list(self.edges.columns)]
        self.assertEqual([c for c in cols if any(f in c for f in FORBIDDEN)], [])

    def test_blocks_and_projects_stay_in_one_fold(self):
        self.assertTrue((self.nodes.groupby("project_key").development_validation_fold.nunique() == 1).all())
        self.assertTrue((self.nodes.groupby("conservative_block_id").development_validation_fold.nunique() == 1).all())


class ProtocolTests(unittest.TestCase):
    def test_protocol_declares_required_fields(self):
        p = json.loads((ROOT / "research/gnn/cambridge_protocol.json").read_text(encoding="utf-8"))
        for k in ("models", "optimizer", "loss", "batch_size_graphs", "max_epochs", "early_stopping", "seeds",
                  "folds", "baselines", "primary_metric", "success_criterion"):
            self.assertIn(k, p)
        self.assertEqual(p["features"], ["activity_description", "project_type", "uk_region"])


if __name__ == "__main__":
    unittest.main()
