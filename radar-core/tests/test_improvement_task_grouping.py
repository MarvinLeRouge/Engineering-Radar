from radar_core.improvement_task_grouping import compute_task_group_key


def test_same_criterion_and_file_produce_the_same_key():
    first = compute_task_group_key(1, "src/a.py")
    second = compute_task_group_key(1, "src/a.py")

    assert first == second


def test_different_criterion_produces_a_different_key():
    first = compute_task_group_key(1, "src/a.py")
    second = compute_task_group_key(2, "src/a.py")

    assert first != second


def test_different_file_produces_a_different_key():
    first = compute_task_group_key(1, "src/a.py")
    second = compute_task_group_key(1, "src/b.py")

    assert first != second


def test_a_none_file_does_not_crash_and_still_differs_from_a_real_file():
    without_file = compute_task_group_key(1, None)
    with_file = compute_task_group_key(1, "src/a.py")

    assert without_file != with_file


def test_atomic_fingerprint_is_reused_verbatim_as_the_group_key():
    key = compute_task_group_key(1, "src/a.py", atomic_finding_fingerprint="abc123deadbeef00")

    assert key == "abc123deadbeef00"


def test_group_key_is_a_short_hex_string_when_not_atomic():
    key = compute_task_group_key(1, "src/a.py")

    assert len(key) == 16
    assert all(c in "0123456789abcdef" for c in key)
