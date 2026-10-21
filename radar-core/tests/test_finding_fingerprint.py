from radar_core.enums import FindingSeverity
from radar_core.finding_fingerprint import compute_fingerprint


def test_same_inputs_produce_the_same_fingerprint():
    first = compute_fingerprint(1, FindingSeverity.LOW, "src/a.py", "unused-var:temp")
    second = compute_fingerprint(1, FindingSeverity.LOW, "src/a.py", "unused-var:temp")

    assert first == second


def test_different_criterion_produces_a_different_fingerprint():
    first = compute_fingerprint(1, FindingSeverity.LOW, "src/a.py", "unused-var:temp")
    second = compute_fingerprint(2, FindingSeverity.LOW, "src/a.py", "unused-var:temp")

    assert first != second


def test_different_severity_produces_a_different_fingerprint():
    first = compute_fingerprint(1, FindingSeverity.LOW, "src/a.py", "unused-var:temp")
    second = compute_fingerprint(1, FindingSeverity.HIGH, "src/a.py", "unused-var:temp")

    assert first != second


def test_different_file_produces_a_different_fingerprint():
    first = compute_fingerprint(1, FindingSeverity.LOW, "src/a.py", "unused-var:temp")
    second = compute_fingerprint(1, FindingSeverity.LOW, "src/b.py", "unused-var:temp")

    assert first != second


def test_different_label_produces_a_different_fingerprint():
    first = compute_fingerprint(1, FindingSeverity.LOW, "src/a.py", "unused-var:temp")
    second = compute_fingerprint(1, FindingSeverity.LOW, "src/a.py", "unused-var:other")

    assert first != second


def test_a_none_file_does_not_crash_and_still_differs_from_a_real_file():
    without_file = compute_fingerprint(1, FindingSeverity.LOW, None, "label")
    with_file = compute_fingerprint(1, FindingSeverity.LOW, "src/a.py", "label")

    assert without_file != with_file


def test_fingerprint_is_a_short_hex_string():
    fingerprint = compute_fingerprint(1, FindingSeverity.LOW, "src/a.py", "label")

    assert len(fingerprint) == 16
    assert all(c in "0123456789abcdef" for c in fingerprint)
