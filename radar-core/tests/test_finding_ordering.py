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


def test_ties_on_magnitude_break_alphabetically_by_file():
    zebra = _finding(FindingSeverity.LOW, magnitude=10.0, finding_id=1)
    zebra.file = "zebra.py"
    apple = _finding(FindingSeverity.LOW, magnitude=10.0, finding_id=2)
    apple.file = "apple.py"

    result = sort_findings_by_priority([zebra, apple])

    assert [f.id for f in result] == [2, 1]


def test_ties_on_file_break_alphabetically_by_description():
    second = _finding(FindingSeverity.LOW, description="z finding", magnitude=5.0, finding_id=1)
    second.file = "a.py"
    first = _finding(FindingSeverity.LOW, description="a finding", magnitude=5.0, finding_id=2)
    first.file = "a.py"

    result = sort_findings_by_priority([second, first])

    assert [f.id for f in result] == [2, 1]


def test_ties_with_no_magnitude_at_all_break_alphabetically_by_file():
    zebra = _finding(FindingSeverity.LOW, finding_id=1)
    zebra.file = "zebra.py"
    apple = _finding(FindingSeverity.LOW, finding_id=2)
    apple.file = "apple.py"

    result = sort_findings_by_priority([zebra, apple])

    assert [f.id for f in result] == [2, 1]


def _seed_scoring_run_and_criterion(db_session):
    from radar_core.enums import ScoringModel
    from radar_core.models.audit import Audit
    from radar_core.models.methodology import Category, Criterion, MethodologyVersion
    from radar_core.models.repository import Repository
    from radar_core.models.scoring import ScoringRun

    repo = Repository(name="repo", path="/tmp/repo")
    version = MethodologyVersion(version_label="1.0")
    db_session.add_all([repo, version])
    db_session.flush()
    audit = Audit(repository_id=repo.id, commit_sha="abc", is_dirty=False)
    category = Category(methodology_version_id=version.id, name="Quality", weight=1.0, order=1)
    db_session.add_all([audit, category])
    db_session.flush()
    criterion = Criterion(
        category_id=category.id,
        name="Typing",
        description="...",
        weight=1.0,
        scoring_model=ScoringModel.FIXED_SCALE,
    )
    scoring_run = ScoringRun(audit_id=audit.id, methodology_version_id=version.id)
    db_session.add_all([criterion, scoring_run])
    db_session.flush()
    return scoring_run, criterion


def test_sql_priority_order_matches_the_python_sort(db_session):
    from radar_core.finding_ordering import PRIORITY_ORDER_BY
    from sqlmodel import select

    scoring_run, criterion = _seed_scoring_run_and_criterion(db_session)
    specs = [
        (FindingSeverity.LOW, None, "b.py", "same"),
        (FindingSeverity.CRITICAL, None, None, "no file"),
        (FindingSeverity.MEDIUM, 11.0, "a.py", "small"),
        (FindingSeverity.MEDIUM, 42.0, "z.py", "big"),
        (FindingSeverity.MEDIUM, None, "a.py", "no magnitude"),
        (FindingSeverity.LOW, None, "b.py", "same"),
        (FindingSeverity.LOW, None, "B.py", "uppercase"),
        (FindingSeverity.INFO, 3.0, "é.py", "accent"),
        (FindingSeverity.HIGH, 1.0, "", "empty file"),
    ]
    for severity, magnitude, file, description in specs:
        finding = _finding(severity, description=description, magnitude=magnitude)
        finding.scoring_run_id = scoring_run.id
        finding.criterion_id = criterion.id
        finding.file = file
        db_session.add(finding)
    db_session.flush()

    by_id = db_session.exec(select(Finding).order_by(Finding.id)).all()
    from_sql = db_session.exec(select(Finding).order_by(*PRIORITY_ORDER_BY)).all()

    assert [f.id for f in from_sql] == [f.id for f in sort_findings_by_priority(by_id)]
