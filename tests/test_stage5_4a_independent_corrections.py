"""Regressions for the independent CPM review findings."""

from copy import deepcopy
import unittest

from pmi_core.scheduling.calendar import SchedulingError
from pmi_core.scheduling.fixture import adapt
from test_stage5_4a import CONFIG, HANDOVER, PREPARED, link, run, task


class IndependentCPMCorrections(unittest.TestCase):
    def test_reject_off_grid_ticks_and_boundaries(self):
        for tick in (7, 45):
            with self.subTest(tick=tick), self.assertRaises(SchedulingError) as caught:
                run([task("A", 30)], tick=tick)
            self.assertEqual(caught.exception.code, "TICK_MISALIGNED")
        with self.assertRaises(SchedulingError) as caught:
            run([task("A", 30, allowed_hours=[["08:00", "14:05"]])], tick=15)
        self.assertEqual(caught.exception.code, "TICK_MISALIGNED")

    def test_controlled_calendar_override_requires_equal_recurring_windows(self):
        prepared = deepcopy(PREPARED)
        prepared["calendar"]["working_windows"][0]["end"] = "15:00"
        with self.assertRaisesRegex(ValueError, "different recurring working windows"):
            adapt(HANDOVER, prepared, CONFIG)

    def test_absolute_release_leaves_predecessor_float(self):
        result = run(
            [task("POUR", 60), task("RELEASE", 4320, kind="strength_release",
                                    release_event_id="strength"), task("STRIP", 60)],
            [link("POUR", "RELEASE"), link("RELEASE", "STRIP")],
            release_events={"strength": {"status": "recorded_pass", "at": "2027-01-08T10:30"}},
        )
        rows = {row["id"]: row for row in result["activities"]}
        self.assertEqual(rows["RELEASE"]["earliest_start"], "2027-01-04T09:00+01:00")
        self.assertEqual(rows["RELEASE"]["earliest_finish"], "2027-01-08T10:30+01:00")
        self.assertEqual(rows["RELEASE"]["latest_start"], "2027-01-05T10:30+01:00")
        self.assertEqual(rows["RELEASE"]["release_wait_minutes"], 1530)
        self.assertEqual(rows["STRIP"]["total_float_minutes"], 0)
