"""Runner for docvet, which checks Python docstring presence."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from typing import Literal

from radar_audit.runner import RawToolOutput
from radar_audit.runners.shared import raw_fallback, relativize_file_field, run_timed, tool_output
from radar_audit.scope import TESTS_AND_MIGRATIONS, exclusion_glob

# docvet's built-in `exclude` default ("tests", "scripts"), minus "tests": the audit
# excludes tests through radar_audit.scope (orchestrator), like every other runner.
_DOCVET_DEFAULT_EXCLUDES = ("scripts",)


class DocvetRunner:
    """Runs docvet's docstring presence check with an audit-owned scratch config.

    Criterion 5.3, Python.
    """

    tool_name = "docvet"
    tool_version = "1.0.0"
    supported_stacks: frozenset[str] = frozenset({"python"})
    scope: Literal["repo", "subproject"] = "subproject"
    excluded_zones = TESTS_AND_MIGRATIONS
    timeout_s = 30

    def run(self, target_path: Path, exclude_paths: list[Path]) -> RawToolOutput:
        """Runs docvet's presence check with a scratch config restating its default excludes."""
        # A scratch `exclude` replaces docvet's defaults, so restate them.
        exclude_entries = list(_DOCVET_DEFAULT_EXCLUDES)
        for excluded in exclude_paths:
            try:
                relative = excluded.relative_to(target_path)
            except ValueError:
                continue
            # docvet only matches multi-segment entries as globs, not as prefixes.
            entry = "*" if relative == Path(".") else exclusion_glob(excluded, relative, "/*")
            if entry not in exclude_entries:
                exclude_entries.append(entry)

        config_content = f"[tool.docvet]\nexclude = {json.dumps(exclude_entries)}\n"

        with tempfile.NamedTemporaryFile(
            "w", suffix=".toml", delete=False, dir=target_path
        ) as config_file:
            config_file.write(config_content)
            config_path = Path(config_file.name)

        try:
            command = [
                "uvx",
                "docvet",
                "--format",
                "json",
                "--config",
                config_path.name,
                "presence",
                "--all",
            ]
            completed, duration_ms = run_timed(command, self.timeout_s, cwd=target_path)
        finally:
            config_path.unlink(missing_ok=True)

        try:
            raw_output = json.loads(completed.stdout)
        except json.JSONDecodeError:
            raw_output = raw_fallback(completed)
        else:
            relativize_file_field(raw_output.get("findings", []), target_path)

        return tool_output(command, raw_output, completed, duration_ms)
