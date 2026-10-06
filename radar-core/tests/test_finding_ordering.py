from radar_core.enums import Confidence, FindingSeverity, FindingStatus, HumanVerdict
from radar_core.finding_ordering import sort_findings_by_priority
from radar_core.models.finding import Finding


def _finding(severity, description="stub", magnitude=None, finding_id=None):
    return Finding(
        id=finding_id,
        scoring_run_id=1,
        criterion_id=1,
        severity=severity,
        description=description,
        magnitude=magnitude,
        confidence=Confidence.HIGH,
        status=FindingStatus.OPEN,
        human_verdict=HumanVerdict.UNREVIEWED,
    )


def test_sorts_by_severity_critical_first():
    low = _finding(FindingSeverity.LOW, finding_id=1)
    critical = _finding(FindingSeverity.CRITICAL, finding_id=2)
    medium = _finding(FindingSeverity.MEDIUM, finding_id=3)
    high = _finding(FindingSeverity.HIGH, finding_id=4)
    info = _finding(FindingSeverity.INFO, finding_id=5)

    result = sort_findings_by_priority([low, critical, medium, high, info])

    assert [f.id for f in result] == [2, 4, 3, 1, 5]


def test_sorts_by_magnitude_descending_within_the_same_severity():
    small = _finding(FindingSeverity.MEDIUM, magnitude=11.0, finding_id=1)
    big = _finding(FindingSeverity.MEDIUM, magnitude=42.0, finding_id=2)
    medium_mag = _finding(FindingSeverity.MEDIUM, magnitude=28.0, finding_id=3)

    result = sort_findings_by_priority([small, big, medium_mag])

    assert [f.id for f in result] == [2, 3, 1]


def test_findings_without_magnitude_sort_after_findings_with_magnitude_in_the_same_severity():
    no_magnitude = _finding(FindingSeverity.MEDIUM, magnitude=None, finding_id=1)
    with_magnitude = _finding(FindingSeverity.MEDIUM, magnitude=5.0, finding_id=2)

    result = sort_findings_by_priority([no_magnitude, with_magnitude])

    assert [f.id for f in result] == [2, 1]


def test_stable_order_preserved_when_neither_has_a_magnitude():
    first = _finding(FindingSeverity.LOW, finding_id=1)
    second = _finding(FindingSeverity.LOW, finding_id=2)
    third = _finding(FindingSeverity.LOW, finding_id=3)

    result = sort_findings_by_priority([first, second, third])

    assert [f.id for f in result] == [1, 2, 3]


def test_severity_takes_priority_over_magnitude():
    high_with_low_magnitude = _finding(FindingSeverity.HIGH, magnitude=1.0, finding_id=1)
    critical_with_no_magnitude = _finding(FindingSeverity.CRITICAL, magnitude=None, finding_id=2)

    result = sort_findings_by_priority([high_with_low_magnitude, critical_with_no_magnitude])

    assert [f.id for f in result] == [2, 1]


def test_empty_list_returns_empty_list():
    assert sort_findings_by_priority([]) == []
