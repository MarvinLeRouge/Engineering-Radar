import subprocess

from radar_audit.runners.trivy_image_runner import TrivyImageRunner

from tests.git_helpers import init_git_repo


def _build_minimal_image(tag: str, context_dir) -> None:
    subprocess.run(
        ["docker", "build", "-t", tag, "-f", "-", str(context_dir)],
        input=b"FROM alpine:latest\n",
        check=True,
        capture_output=True,
    )


def test_reports_image_not_found_when_no_local_image_matches(tmp_path):
    repo_path = tmp_path / "repo-with-no-image"
    init_git_repo(repo_path, files={"src/a.py": "x = 1\n"})

    runner = TrivyImageRunner()
    result = runner.run(repo_path, exclude_paths=[])

    assert result.exit_code == 0
    assert result.raw_output == {"image_found": False}


def test_reports_vulnerabilities_when_a_matching_local_image_exists(tmp_path):
    repo_path = tmp_path / "trivyimgtest"
    init_git_repo(repo_path, files={"Dockerfile": "FROM alpine:latest\n"})
    image_tag = f"{repo_path.name.lower()}:latest"
    subprocess.run(
        ["docker", "build", "-t", image_tag, str(repo_path)], check=True, capture_output=True
    )
    try:
        runner = TrivyImageRunner()
        result = runner.run(repo_path, exclude_paths=[])

        assert result.raw_output["image_found"] is True
        assert result.raw_output["image"] == image_tag
        assert isinstance(result.raw_output["vulnerabilities"], list)
        for vuln in result.raw_output["vulnerabilities"]:
            assert vuln["severity"] in {"HIGH", "CRITICAL"}
    finally:
        subprocess.run(["docker", "rmi", image_tag], capture_output=True)


def test_root_subproject_does_not_match_a_sibling_subprojects_image_by_substring(tmp_path):
    """A monorepo's root subproject (e.g. 'radarfixtureapp', from a root-level
    manifest) must not accidentally match a sibling subproject's hyphenated
    image name ('radarfixtureapp-backend') just because its own name is a
    substring of it. The distinctive 'radarfixtureapp' name is chosen so this
    test can't collide with any real, unrelated image already sitting on the
    machine running the suite.
    """
    root_path = tmp_path / "radarfixtureapp"
    backend_path = root_path / "backend"
    backend_path.mkdir(parents=True)
    image_tag = "radarfixtureapp-backend:latest"
    _build_minimal_image(image_tag, backend_path)
    try:
        runner = TrivyImageRunner()

        root_result = runner.run(root_path, exclude_paths=[])
        assert root_result.raw_output == {"image_found": False}

        backend_result = runner.run(backend_path, exclude_paths=[])
        assert backend_result.raw_output["image_found"] is True
        assert backend_result.raw_output["image"] == image_tag
    finally:
        subprocess.run(["docker", "rmi", image_tag], capture_output=True)


def test_matches_a_registry_prefixed_image_by_slash_suffix(tmp_path):
    root_path = tmp_path / "radarfixtureapp"
    backend_path = root_path / "backend"
    backend_path.mkdir(parents=True)
    image_tag = "example.registry/radarfixtureapp/backend:latest"
    _build_minimal_image(image_tag, backend_path)
    try:
        runner = TrivyImageRunner()
        result = runner.run(backend_path, exclude_paths=[])

        assert result.raw_output["image_found"] is True
        assert result.raw_output["image"] == image_tag
    finally:
        subprocess.run(["docker", "rmi", image_tag], capture_output=True)


def test_distinguishes_two_sibling_subprojects_with_similarly_named_images(tmp_path):
    root_path = tmp_path / "radarfixtureapp"
    backend_path = root_path / "backend"
    frontend_path = root_path / "frontend"
    backend_path.mkdir(parents=True)
    frontend_path.mkdir(parents=True)
    backend_tag = "radarfixtureapp-backend:latest"
    frontend_tag = "radarfixtureapp-frontend:latest"
    _build_minimal_image(backend_tag, backend_path)
    _build_minimal_image(frontend_tag, frontend_path)
    try:
        runner = TrivyImageRunner()

        assert runner.run(backend_path, exclude_paths=[]).raw_output["image"] == backend_tag
        assert runner.run(frontend_path, exclude_paths=[]).raw_output["image"] == frontend_tag
    finally:
        subprocess.run(["docker", "rmi", backend_tag, frontend_tag], capture_output=True)


def test_skips_rescanning_an_image_already_scanned_for_a_sibling_subproject(tmp_path):
    """Two different subproject paths that happen to resolve to the exact same
    local image (e.g. duplicate directory basenames in an unusual layout) must
    not scan it twice and double-count its vulnerabilities.
    """
    root_path = tmp_path / "radarfixtureapp"
    # Deliberately different parents ("services" vs "legacy") so neither
    # resolves via the precise repo-subproject compound key, forcing both
    # through the plain-name fallback that this test exercises.
    first_path = root_path / "services" / "radarfixtureleaf"
    second_path = root_path / "legacy" / "radarfixtureleaf"
    first_path.mkdir(parents=True)
    second_path.mkdir(parents=True)
    image_tag = "radarfixtureapp-radarfixtureleaf:latest"
    _build_minimal_image(image_tag, first_path)
    try:
        runner = TrivyImageRunner()

        first_result = runner.run(first_path, exclude_paths=[])
        assert first_result.raw_output["image_found"] is True
        assert first_result.raw_output["image"] == image_tag

        second_result = runner.run(second_path, exclude_paths=[])
        assert second_result.raw_output == {"image_found": False}
    finally:
        subprocess.run(["docker", "rmi", image_tag], capture_output=True)


def test_reports_tool_identity():
    runner = TrivyImageRunner()

    assert runner.tool_name == "trivy-image"
    assert runner.scope == "subproject"
    assert runner.supported_stacks == frozenset({"python", "javascript", "php", "unknown"})
