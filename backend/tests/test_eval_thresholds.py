"""Threshold test - the blueprint's Phase A gate. Must pass before pilot."""

from tests.eval_harness import check_thresholds, run


def test_eval_meets_acceptance_thresholds():
    metrics = run()
    violations = check_thresholds(metrics)
    report = "\n".join(f"  {k}={v}" for k, v in metrics.values.items())
    detail_report = "\n".join(metrics.details)
    assert not violations, (
        f"acceptance thresholds not met:\n{violations}\nmetrics:\n{report}\n"
        f"details:\n{detail_report}")
