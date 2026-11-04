"""Runner for ESLint's complexity rule, using an audit-owned config with a zero threshold."""

from __future__ import annotations

import json
import re
import tempfile
from pathlib import Path
from typing import Literal

from radar_audit.runner import RawToolOutput
from radar_audit.runners.shared import raw_fallback, relativize_file_field, run_timed, tool_output
from radar_audit.scope import TESTS_AND_MIGRATIONS, exclusion_glob

_AUDIT_CONFIG = 'module.exports = [{ rules: { complexity: ["error", 0] } }];\n'
_COMPLEXITY_PATTERN = re.compile(r"^(.+) has a complexity of (\d+)")
_ALWAYS_EXCLUDED_DIRNAMES = ("node_modules", "vendor", "dist", "build")


class EslintComplexityRunner:
    """Run ESLint with audit-owned ["error", 0] complexity config (criterion 2.3)."""

    tool_name = "eslint-complexity"
    tool_version = "1.0.0"
    supported_stacks: frozenset[str] = frozenset({"javascript"})
    scope: Literal["repo", "subproject"] = "subproject"
    excluded_zones = TESTS_AND_MIGRATIONS
    timeout_s = 60

    def run(self, target_path: Path, exclude_paths: list[Path]) -> RawToolOutput:
        """Runs ESLint with the complexity rule set to zero and collects each function's score."""
        with tempfile.NamedTemporaryFile(
            "w", suffix=".config.cjs", delete=False, dir=target_path
        ) as config_file:
            config_file.write(_AUDIT_CONFIG)
            config_path = Path(config_file.name)

        try:
            command = [
                "npx",
                "--package=eslint",
                "--",
                "eslint",
                "-c",
                str(config_path),
                str(target_path),
                "--format",
                "json",
            ]
            for name in _ALWAYS_EXCLUDED_DIRNAMES:
                command.extend(["--ignore-pattern", f"**/{name}/**"])
            for excluded in exclude_paths:
                try:
                    relative = excluded.relative_to(target_path)
                except ValueError:
                    continue  # not under target_path, skip
                command.extend(["--ignore-pattern", exclusion_glob(excluded, relative, "/**")])

            completed, duration_ms = run_timed(command, self.timeout_s, cwd=target_path)
        finally:
            config_path.unlink(missing_ok=True)

        try:
            results = json.loads(completed.stdout)
        except json.JSONDecodeError:
            return tool_output(command, raw_fallback(completed), completed, duration_ms)

        complexities = []
        for entry in results:
            for message in entry.get("messages", []):
                match = _COMPLEXITY_PATTERN.search(message.get("message", ""))
                if match:
                    complexities.append(
                        {
                            "file": entry["filePath"],
                            "line": message.get("line"),
                            # e.g. "Method 'foo'"/"Arrow function" -- the rule's own
                            # message prefix, with no enclosing-class qualifier.
                            "name": match.group(1),
                            "complexity": int(match.group(2)),
                        }
                    )

        relativize_file_field(complexities, target_path)
        return tool_output(command, {"complexities": complexities}, completed, duration_ms)
