from radar_audit.scope import (
    MIGRATIONS,
    TESTS,
    TESTS_AND_MIGRATIONS,
    exclusion_glob,
    is_test_path,
    out_of_scope_paths,
)


def write_files(root, files):
    for relative, content in files.items():
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)


def _relative(paths, root):
    return sorted(str(p.relative_to(root.resolve())) for p in paths)


def test_finds_test_directories_and_colocated_test_files(tmp_path):
    write_files(
        tmp_path,
        {
            "src/app/service.py": "",
            "src/app/test_service.py": "",
            "src/app/service_test.py": "",
            "tests/test_api.py": "",
            "tests/conftest.py": "",
            "frontend/src/components/__tests__/Card.spec.ts": "",
            "frontend/e2e/report.spec.ts": "",
            "backend/src/users/users.service.ts": "",
            "backend/src/users/users.service.spec.ts": "",
            "backend/test/app.e2e-spec.ts": "",
            "web/src/utils.test.js": "",
        },
    )

    found = out_of_scope_paths(tmp_path, frozenset({TESTS}))

    assert _relative(found, tmp_path) == [
        "backend/src/users/users.service.spec.ts",
        "backend/test",
        "frontend/e2e",
        "frontend/src/components/__tests__",
        "src/app/service_test.py",
        "src/app/test_service.py",
        "tests",
        "web/src/utils.test.js",
    ]


def test_finds_alembic_and_framework_migrations(tmp_path):
    write_files(
        tmp_path,
        {
            "radar-core/alembic/env.py": "",
            "radar-core/alembic/versions/001_init.py": "",
            "app/alembic/__init__.py": "",
            "database/migrations/2024_01_01_create_users.php": "",
            "shop/migrations/0001_initial.py": "",
        },
    )

    found = out_of_scope_paths(tmp_path, frozenset({MIGRATIONS}))

    # A package merely named "alembic" (no versions/ dir) is application code.
    assert _relative(found, tmp_path) == [
        "database/migrations",
        "radar-core/alembic",
        "shop/migrations",
    ]


def test_skips_dependencies_and_returns_nothing_without_zones(tmp_path):
    write_files(
        tmp_path,
        {
            "node_modules/pkg/test/index.test.js": "",
            ".venv/lib/tests/test_x.py": "",
            "tests/test_a.py": "",
        },
    )

    assert _relative(out_of_scope_paths(tmp_path, TESTS_AND_MIGRATIONS), tmp_path) == ["tests"]
    assert out_of_scope_paths(tmp_path, frozenset()) == []


def test_exclusion_glob_suffixes_directories_only(tmp_path):
    write_files(tmp_path, {"tests/test_a.py": "", "src/a.spec.ts": ""})

    assert exclusion_glob(tmp_path / "tests", "tests", "/**") == "tests/**"
    assert exclusion_glob(tmp_path / "src/a.spec.ts", "src/a.spec.ts", "/**") == "src/a.spec.ts"


def test_every_runner_declares_the_documented_scope():
    from radar_audit.cli import DEFAULT_RUNNERS

    # Mirrors the "Audit scope" table in docs/quality-framework.md.
    expected = {
        "radon-cc": TESTS_AND_MIGRATIONS,
        "eslint-complexity": TESTS_AND_MIGRATIONS,
        "phpmd-codesize": TESTS_AND_MIGRATIONS,
        "vulture": frozenset({MIGRATIONS}),
        "knip": frozenset({MIGRATIONS}),
        "radon-raw": TESTS_AND_MIGRATIONS,
        "static-loc-count": TESTS_AND_MIGRATIONS,
        "docvet": TESTS_AND_MIGRATIONS,
        "phpdoc-checker": TESTS_AND_MIGRATIONS,
        "jscpd": TESTS_AND_MIGRATIONS,
        "mypy": TESTS_AND_MIGRATIONS,
        "tsc": TESTS_AND_MIGRATIONS,
        "phpstan": TESTS_AND_MIGRATIONS,
        "ruff-check": frozenset({MIGRATIONS}),
        "eslint": frozenset({MIGRATIONS}),
    }

    declared = {
        runner.tool_name: getattr(runner, "excluded_zones", frozenset())
        for runner in DEFAULT_RUNNERS
    }

    assert {name: zones for name, zones in declared.items() if zones} == expected


def test_is_test_path_matches_test_dirs_and_test_file_names():
    assert is_test_path("tests/test_a.py")
    assert is_test_path("src/components/__tests__/Card.spec.ts")
    assert is_test_path("src/users/users.service.spec.ts")
    assert is_test_path("conftest.py")
    assert not is_test_path("src/radar_core/models/finding.py")
    assert not is_test_path("src/testing_utils.py")


def test_returns_paths_in_the_form_of_the_given_target(tmp_path):
    write_files(tmp_path, {"app/tests/test_a.py": ""})
    link = tmp_path / "link"
    link.symlink_to(tmp_path / "app")

    found = out_of_scope_paths(link, frozenset({TESTS}))

    # Runners call excluded.relative_to(target_path): a resolved path would break that.
    assert found == [link / "tests"]


def test_skips_dot_and_cache_directories_and_non_code_spec_files(tmp_path):
    write_files(
        tmp_path,
        {
            ".tox/py312/lib/tests/test_x.py": "",
            "htmlcov/a.spec.js": "",
            "docs/openapi.spec.yaml": "",
            "src/a.spec.ts": "",
        },
    )

    assert _relative(out_of_scope_paths(tmp_path, frozenset({TESTS})), tmp_path) == [
        "src/a.spec.ts"
    ]
    assert not is_test_path("docs/openapi.spec.yaml")
