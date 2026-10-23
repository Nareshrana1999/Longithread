from datetime import datetime, timedelta

from app.analytics.cohort import summarize_cohort


class _Task:
    def __init__(self, status, due_at=None, rule_id="r"):
        self.status, self.due_at, self.rule_id = status, due_at, rule_id


class _Obs:
    def __init__(self, code, when, val, status="validated"):
        self.code, self.observed_at, self.value_numeric, self.status = code, when, val, status


AS_OF = datetime(2024, 6, 1)


def test_completion_and_overdue_math():
    patients = [{
        "condition": "diabetes",
        "observations": [_Obs("HBA1C", AS_OF - timedelta(days=30), 7.0)],
        "tasks": [_Task("pending", AS_OF - timedelta(days=1)),   # overdue
                 _Task("pending", AS_OF + timedelta(days=10)),   # not yet
                 _Task("done")],
    }]
    s = summarize_cohort(patients, as_of=AS_OF)
    assert s.n_patients == 1
    assert s.tasks_created == 3
    assert s.tasks_overdue == 1
    assert abs(s.completion_rate - 1 / 3) < 1e-9
    assert s.by_condition["diabetes"]["completion_rate"] == round(1 / 3, 4)


def test_monitoring_gap_detection():
    recent = [_Obs("HBA1C", AS_OF - timedelta(days=60), 7.2)]
    stale = [_Obs("HBA1C", AS_OF - timedelta(days=500), 6.5)]
    s = summarize_cohort(
        [{"condition": "d", "observations": recent, "tasks": []},
         {"condition": "d", "observations": stale, "tasks": []}], as_of=AS_OF)
    assert s.monitoring_gap_rate == 0.5   # one of two patients lacks a 12-month HbA1c


def test_trend_aggregation_present():
    obs = [_Obs("HBA1C", AS_OF - timedelta(days=200), 7.0),
           _Obs("HBA1C", AS_OF - timedelta(days=10), 8.0)]
    s = summarize_cohort([{"condition": "d", "observations": obs, "tasks": []}], as_of=AS_OF)
    assert s.mean_latest_hba1c == 8.0
    assert s.mean_hba1c_slope_per_month is not None and s.mean_hba1c_slope_per_month > 0
