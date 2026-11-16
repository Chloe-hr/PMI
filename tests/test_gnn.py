import sys
import unittest
from pathlib import Path

import numpy as np
import pandas as pd
import torch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "research" / "gnn"))
from dslib import parse_duration  # noqa: E402
from graph_schema import FEATURES, bridge_zero_duration, categorize, from_pmi_folder, to_graph  # noqa: E402
from model import make  # noqa: E402


def acts():
    return pd.DataFrame({
        "activity_id": ["1", "2", "M", "3"],
        "name": ["Grondwerken", "Storten funderingsplaat", "Milestone", "Plaatsen convectoren"],
        "planned_days": [5.0, 10.0, 0.0, 4.0],
        "predecessors": ["", "1", "2", "M"],
        "actual_days": [5.0, 12.0, np.nan, np.nan],
    })


class GraphTests(unittest.TestCase):
    def test_milestones_are_bridged(self):
        a = bridge_zero_duration(acts()).set_index("activity_id")
        self.assertNotIn("M", a.index)
        self.assertEqual(a.at["3", "predecessors"], "2")

    def test_dutch_names_and_short_keywords(self):
        self.assertEqual(categorize("Plaatsen convectoren"), "services")   # 'plaatsen' must not mean slab
        self.assertEqual(categorize("Storten en trillen wanden"), "structure")
        self.assertEqual(categorize("Section 58"), "other")

    def test_graph_shapes_labels_and_direction(self):
        g = to_graph(acts(), "P")
        self.assertEqual(g.x.shape, (3, len(FEATURES)))
        self.assertEqual(g.edge_index.shape[1], 4)                        # 2 links x 2 directions
        self.assertAlmostEqual(float(g.y[1]), float(np.log(12 / 10)), places=5)
        self.assertTrue(torch.isnan(g.y[2]))                              # unlabelled stays NaN
        for kind in ("gnn", "mlp"):
            self.assertEqual(make(kind, len(FEATURES))(g).shape, (3,))

    def test_duration_parsing(self):
        self.assertEqual(parse_duration("22d 4h"), 22.5)
        self.assertEqual(parse_duration("4h"), 0.5)
        self.assertEqual(parse_duration("0"), 0.0)

    def test_overrun_auc_from_saved_predictions(self):
        from evaluate_overrun import overrun_auc
        planned = np.array([10.0, 10, 10, 10, 10, 10, 10, 10])
        actual = np.array([10.0, 15, 10, 15, 10, 15, 10, 15])          # every second activity overruns
        perfect = np.where(actual > planned, 12.0, 9.0)                # ranks overruns first
        oof = pd.DataFrame({"fold": [0, 0, 0, 0, 1, 1, 1, 1], "planned_days": planned, "actual_days": actual,
                            "pred_category": planned, "pred_mlp": perfect, "pred_gnn": 20.0 - perfect})
        r = overrun_auc(oof)
        self.assertEqual(r["overrun_share"], 0.5)
        self.assertEqual(r["methods"]["mlp"]["per_fold"], {0: 1.0, 1: 1.0})
        self.assertEqual(r["methods"]["gnn"]["pooled"], 0.0)            # inverted ranking
        self.assertEqual(r["methods"]["category"]["pooled"], 0.5)       # constant score = chance

    def test_pmi_schedule_becomes_a_graph(self):
        folder = ROOT / "outputs" / "v1"
        if not (folder / "tasks.csv").is_file():
            self.skipTest("run research/ifc_to_gantt/run.py first")
        g = to_graph(from_pmi_folder(folder), "PMI")
        self.assertEqual(g.x.shape[1], len(FEATURES))
        self.assertNotIn("other", g.categories)


if __name__ == "__main__":
    unittest.main()
