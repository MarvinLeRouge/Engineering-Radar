from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Literal

from radar_audit.runner import RawToolOutput
from radar_audit.runners.docker_support import run_docker_command


class TrivyImageRunner:
    """Scans an already-built local Docker image for HIGH/CRITICAL CVEs (criterion 4.4).

    Never builds an image itself -- if no locally built image matching the
    subproject is found, reports `image_found: False` rather than triggering a
    build (per the precondition documented in toolchain.md).

    Subproject-scoped so a monorepo with several container images (e.g. a
    separate backend/ and frontend/ image) gets each one scanned under its own
    ToolResult, matched by that subproject's own directory name, rather than a
    single ambiguous repo-wide lookup. Not tied to any particular stack: a
    Dockerfile/image isn't a language-specific artifact.
    """

    tool_name = "trivy-image"
    tool_version = "1.0.0"
    supported_stacks: frozenset[str] = frozenset({"python", "javascript", "php", "unknown"})
    scope: Literal["repo", "subproject"] = "subproject"
    timeout_s = 180

    def __init__(self) -> None:
        # Instance state, not module/class state: DEFAULT_RUNNERS builds one
        # instance per CLI process and reuses it across every subproject of
        # one `radar-audit run <repo>` invocation, so this safely resets
        # between separate CLI invocations. The one gap is `--all`, which
        # reuses this same instance across *different* repositories in one
        # process: two unrelated repos that happened to tag an image with the
        # exact same name would see the second one skipped as a false
        # "duplicate". Accepted as a narrow, unlikely edge case rather than
        # threading repo identity through the whole ToolRunner protocol.
        self._scanned_images: set[str] = set()

    def run(self, target_path: Path, exclude_paths: list[Path]) -> RawToolOutput:
        image = self._find_local_image(target_path)
        if image is None:
            return RawToolOutput(
                command="trivy image (skipped, no local image found)",
                raw_output={"image_found": False},
                exit_code=0,
                duration_ms=0,
            )
        if image in self._scanned_images:
            return RawToolOutput(
                command="trivy image (skipped, already scanned for a sibling subproject)",
                raw_output={"image_found": False},
                exit_code=0,
                duration_ms=0,
            )
        self._scanned_images.add(image)

        args = [
            "-v",
            "/var/run/docker.sock:/var/run/docker.sock",
            "aquasec/trivy",
            "image",
            "--format",
            "json",
            "--severity",
            "HIGH,CRITICAL",
            "--scanners",
            "vuln",
            image,
        ]
        completed, duration_ms = run_docker_command(args, timeout_s=self.timeout_s)

        try:
            data = json.loads(completed.stdout)
        except json.JSONDecodeError:
            return RawToolOutput(
                command="docker run ... trivy image",
                raw_output={"image_found": True, "image": image, "stdout": completed.stdout},
                exit_code=completed.returncode,
                duration_ms=duration_ms,
            )

        vulnerabilities = []
        for result in data.get("Results", []) or []:
            for vuln in result.get("Vulnerabilities", []) or []:
                vulnerabilities.append(
                    {
                        "id": vuln["VulnerabilityID"],
                        "severity": vuln["Severity"],
                        "pkg": vuln["PkgName"],
                        "fix_version": vuln.get("FixedVersion") or None,
                    }
                )

        return RawToolOutput(
            command="docker run ... trivy image",
            raw_output={"image_found": True, "image": image, "vulnerabilities": vulnerabilities},
            exit_code=completed.returncode,
            duration_ms=duration_ms,
        )

    def _find_local_image(self, target_path: Path) -> str | None:
        own_name = target_path.name.lower()
        if not own_name:
            return None
        completed = subprocess.run(
            ["docker", "images", "--format", "{{.Repository}}:{{.Tag}}"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        lines = completed.stdout.splitlines()

        # discover_subprojects only ever nests one level deep, so target_path's
        # parent -- when it isn't target_path itself, i.e. target_path isn't a
        # filesystem root -- is reliably either the repo root (for a nested
        # subproject like repo/backend) or some unrelated ancestor (for the
        # repo-root subproject itself, where a compound match should never
        # fire). Trying the compound key first resolves a nested subproject
        # precisely (e.g. "geochallenge-tracker-backend", not just "backend",
        # which would also match an unrelated repo's own "backend" image on
        # the same machine); falling back to the plain name preserves the
        # original single-image-per-repo behavior for the root subproject.
        parent_name = target_path.parent.name.lower() if target_path.parent != target_path else ""
        if parent_name and parent_name != own_name:
            compound_name = f"{parent_name}-{own_name}"
            for line in lines:
                repository = line.split(":", 1)[0].lower()
                if self._matches_name(repository, compound_name) or repository.endswith(
                    f"/{parent_name}/{own_name}"
                ):
                    return line.strip()

        for line in lines:
            repository = line.split(":", 1)[0].lower()
            if self._matches_name(repository, own_name):
                return line.strip()
        return None

    @staticmethod
    def _matches_name(repository: str, name: str) -> bool:
        # A precise component match, not a bare substring: a repo's root
        # subproject name (e.g. "geochallenge-tracker") must not match a
        # sibling subproject's own hyphenated image ("geochallenge-tracker-
        # backend") just because it happens to be a substring of it.
        return (
            repository == name or repository.endswith(f"-{name}") or repository.endswith(f"/{name}")
        )
