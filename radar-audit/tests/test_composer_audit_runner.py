import json
import subprocess
from pathlib import Path

import pytest
from radar_audit.runners import composer_audit_runner
from radar_audit.runners.composer_audit_runner import ComposerAuditRunner

from tests.git_helpers import init_git_repo


def _composer_install(repo_path):
    subprocess.run(
        ["composer", "install", "--no-interaction", "--quiet"], cwd=repo_path, check=True
    )


def test_reports_no_manifest(tmp_path):
    repo_path = tmp_path / "repo"
    init_git_repo(repo_path, files={"src/a.php": "<?php\n"})

    runner = ComposerAuditRunner()
    result = runner.run(repo_path, exclude_paths=[])

    assert result.exit_code == 0
    assert result.raw_output == {"manifest_found": False}


@pytest.mark.slow
def test_reports_no_vulnerabilities_on_a_clean_dependency(tmp_path):
    repo_path = tmp_path / "repo"
    init_git_repo(
        repo_path,
        files={
            "composer.json": json.dumps({"name": "test/clean-test", "require": {"psr/log": "^3.0"}})
        },
    )
    _composer_install(repo_path)

    runner = ComposerAuditRunner()
    result = runner.run(repo_path, exclude_paths=[])

    assert result.exit_code == 0
    assert result.raw_output["manifest_found"] is True
    assert result.raw_output["vulnerabilities"] == []


@pytest.mark.slow
def test_reports_vulnerabilities_on_a_known_vulnerable_dependency(tmp_path):
    repo_path = tmp_path / "repo"
    # "audit.block-insecure: false" is required -- Composer 2.9+ refuses to *install*
    # a package with known advisories by default, confirmed empirically.
    init_git_repo(
        repo_path,
        files={
            "composer.json": json.dumps(
                {
                    "name": "test/vuln-test",
                    "require": {"phpmailer/phpmailer": "6.1.0"},
                    "config": {"audit": {"block-insecure": False}},
                }
            )
        },
    )
    _composer_install(repo_path)

    runner = ComposerAuditRunner()
    result = runner.run(repo_path, exclude_paths=[])

    assert result.exit_code == 1
    vulnerabilities = result.raw_output["vulnerabilities"]
    assert any(v["package"] == "phpmailer/phpmailer" for v in vulnerabilities)
    assert all(v["severity"] in {"CRITICAL", "HIGH", "MEDIUM", "LOW"} for v in vulnerabilities)


def test_reports_a_failed_audit_when_dependencies_are_neither_locked_nor_installed(tmp_path):
    repo_path = tmp_path / "repo"
    init_git_repo(
        repo_path,
        files={
            "composer.json": json.dumps({"name": "test/no-lock", "require": {"psr/log": "^3.0"}})
        },
    )

    runner = ComposerAuditRunner()
    result = runner.run(repo_path, exclude_paths=[])

    assert result.raw_output["manifest_found"] is True
    assert "error" in result.raw_output
    assert "vulnerabilities" not in result.raw_output


@pytest.mark.slow
def test_audits_the_lockfile_when_vendor_is_not_installed(tmp_path):
    repo_path = tmp_path / "repo"
    init_git_repo(
        repo_path,
        files={
            "composer.json": json.dumps(
                {
                    "name": "test/lock-only",
                    "require": {"phpmailer/phpmailer": "6.1.0"},
                    "config": {"audit": {"block-insecure": False}},
                }
            )
        },
    )
    subprocess.run(
        ["composer", "update", "--no-install", "--no-interaction", "--quiet"],
        cwd=repo_path,
        check=True,
    )
    assert not (repo_path / "vendor").exists()

    runner = ComposerAuditRunner()
    result = runner.run(repo_path, exclude_paths=[])

    vulnerabilities = result.raw_output["vulnerabilities"]
    assert any(v["package"] == "phpmailer/phpmailer" for v in vulnerabilities)


def test_reports_no_vulnerabilities_when_only_platform_requirements_are_declared(tmp_path):
    repo_path = tmp_path / "repo"
    init_git_repo(
        repo_path,
        files={"composer.json": json.dumps({"name": "test/platform", "require": {"php": ">=8.1"}})},
    )

    runner = ComposerAuditRunner()
    result = runner.run(repo_path, exclude_paths=[])

    assert result.raw_output == {"manifest_found": True, "vulnerabilities": []}


def test_reports_tool_identity():
    runner = ComposerAuditRunner()

    assert runner.tool_name == "composer-audit"
    assert runner.scope == "subproject"
    assert runner.supported_stacks == frozenset({"php"})


_FIXTURE_DIR = Path(__file__).parent / "fixtures" / "runners" / "composer-audit"


def _project(tmp_path, manifest, lock=False):
    (tmp_path / "composer.json").write_text(
        manifest if isinstance(manifest, str) else json.dumps(manifest)
    )
    if lock:
        (tmp_path / "composer.lock").write_text("{}")


_WITH_DEPS = {"name": "t/t", "require": {"psr/log": "^3.0"}}


def test_normalizes_real_composer_audit_advisories(tmp_path, fake_tool):
    _project(tmp_path, _WITH_DEPS, lock=True)
    stdout = (_FIXTURE_DIR / "advisories.json").read_text()
    calls = fake_tool(composer_audit_runner, stdout=stdout, returncode=1)

    result = ComposerAuditRunner().run(tmp_path, exclude_paths=[])

    assert calls == [["composer", "audit", "--format=json", "--locked"]]
    assert result.command == "composer audit --format=json --locked"
    assert result.exit_code == 1
    # The second advisory has no severity: falls back to MEDIUM.
    assert result.raw_output == {
        "manifest_found": True,
        "vulnerabilities": [
            {
                "id": "PKSA-35kn-2ddp-d3p4",
                "package": "phpmailer/phpmailer",
                "severity": "HIGH",
                "fix_available": True,
            },
            {
                "id": "PKSA-m8by-bb7v-7qt5",
                "package": "phpmailer/phpmailer",
                "severity": "MEDIUM",
                "fix_available": True,
            },
        ],
    }


@pytest.mark.parametrize(
    ("severity", "expected"),
    [
        ("critical", "CRITICAL"),
        ("LOW", "LOW"),
        ("medium", "MEDIUM"),
        ("weird", "MEDIUM"),
        (None, "MEDIUM"),
    ],
)
def test_maps_advisory_severity_case_insensitively(tmp_path, fake_tool, severity, expected):
    _project(tmp_path, _WITH_DEPS)
    advisory = {"advisoryId": "X-1", "packageName": "a/b", "severity": severity}
    fake_tool(composer_audit_runner, stdout=json.dumps({"advisories": {"a/b": [advisory]}}))

    result = ComposerAuditRunner().run(tmp_path, exclude_paths=[])

    assert result.raw_output["vulnerabilities"][0]["severity"] == expected


def test_omits_locked_flag_when_there_is_no_lockfile(tmp_path, fake_tool):
    _project(tmp_path, _WITH_DEPS)
    calls = fake_tool(composer_audit_runner, stdout='{"advisories": []}')

    ComposerAuditRunner().run(tmp_path, exclude_paths=[])

    assert calls == [["composer", "audit", "--format=json"]]


def test_treats_an_empty_advisories_array_as_clean(tmp_path, fake_tool):
    _project(tmp_path, _WITH_DEPS)
    fake_tool(composer_audit_runner, stdout='{"advisories": [], "abandoned": []}')

    result = ComposerAuditRunner().run(tmp_path, exclude_paths=[])

    assert result.raw_output == {"manifest_found": True, "vulnerabilities": []}


def test_empty_stdout_is_clean_when_no_package_is_declared(tmp_path, fake_tool):
    _project(tmp_path, {"name": "t/t", "require": {"php": ">=8.1", "ext-json": "*"}})
    fake_tool(composer_audit_runner, stdout="  \n", stderr="No packages - skipping audit.")

    result = ComposerAuditRunner().run(tmp_path, exclude_paths=[])

    assert result.raw_output == {"manifest_found": True, "vulnerabilities": []}


def test_empty_stdout_is_a_failed_audit_when_packages_are_declared(tmp_path, fake_tool):
    _project(tmp_path, {"name": "t/t", "require-dev": {"phpunit/phpunit": "^11"}})
    fake_tool(composer_audit_runner, stdout="", stderr="boom", returncode=2)

    result = ComposerAuditRunner().run(tmp_path, exclude_paths=[])

    assert result.exit_code == 2
    assert result.raw_output == {
        "manifest_found": True,
        "error": "no packages were audited",
        "stdout": "",
        "stderr": "boom",
    }


@pytest.mark.parametrize("stdout", ["not json", "[]", '"text"', '{"advisories": "nope"}', "{}"])
def test_reports_a_failed_audit_when_stdout_has_no_advisories_report(tmp_path, fake_tool, stdout):
    _project(tmp_path, _WITH_DEPS)
    fake_tool(composer_audit_runner, stdout=stdout, stderr="err", returncode=1)

    result = ComposerAuditRunner().run(tmp_path, exclude_paths=[])

    assert result.raw_output == {
        "manifest_found": True,
        "error": "composer audit produced no advisories report",
        "stdout": stdout,
        "stderr": "err",
    }


@pytest.mark.parametrize("manifest", ["{not json", "[1, 2]", '"x"'])
def test_unreadable_or_non_object_manifest_counts_as_declaring_dependencies(
    tmp_path, fake_tool, manifest
):
    _project(tmp_path, manifest)
    fake_tool(composer_audit_runner, stdout="")

    result = ComposerAuditRunner().run(tmp_path, exclude_paths=[])

    assert result.raw_output["error"] == "no packages were audited"


@pytest.mark.parametrize("requirements", [None, [], "psr/log", ["psr/log"]])
def test_malformed_require_sections_declare_no_package(tmp_path, fake_tool, requirements):
    _project(tmp_path, {"name": "t/t", "require": requirements})
    fake_tool(composer_audit_runner, stdout="")

    result = ComposerAuditRunner().run(tmp_path, exclude_paths=[])

    assert result.raw_output == {"manifest_found": True, "vulnerabilities": []}


def test_manifest_read_errors_count_as_declaring_dependencies(tmp_path, fake_tool):
    (tmp_path / "composer.json").mkdir()
    fake_tool(composer_audit_runner, stdout="")

    result = ComposerAuditRunner().run(tmp_path, exclude_paths=[])

    assert result.raw_output["error"] == "no packages were audited"
