"""Deterministic Markdown report rendering."""

from typing import Any, Iterable, Mapping, Sequence


def _value(item: Any, key: str, default: Any = "") -> Any:
    if isinstance(item, Mapping):
        return item.get(key, default)
    return getattr(item, key, default)


def _clean(value: Any) -> str:
    return str(value if value is not None else "").replace("\r", "").strip()


def _evidence_lines(evidence: Sequence[Any]) -> str:
    lines = []
    for item in evidence:
        path = _clean(_value(item, "file", "unknown file"))
        line = _value(item, "line", "")
        reason = _clean(_value(item, "reason", "evidence"))
        location = "{}:{}".format(path, line) if line else path
        lines.append("  - `{}` — {}".format(location, reason))
    return "\n".join(lines)


def generate_markdown_report(investigation: Mapping[str, Any]) -> str:
    """Render persisted investigation data without external templates."""

    results = _value(investigation, "results", {}) or {}
    source = _value(investigation, "source", {}) or {}
    title = _clean(_value(investigation, "title", "Code-Aid investigation"))
    lines = [
        "# Code-Aid Investigation: {}".format(title),
        "",
        "- **Investigation ID:** `{}`".format(_clean(_value(investigation, "id", ""))),
        "- **Status:** `{}`".format(_clean(_value(investigation, "status", ""))),
        "- **Source:** `{}`{}".format(
            _clean(_value(source, "source_type", "unknown")),
            " (`{}`)".format(_clean(_value(source, "sample_id"))) if _value(source, "sample_id") else "",
        ),
        "",
        "## Source and traceback",
        "",
        "- Files ingested: **{}**".format(_value(source, "file_count", 0)),
    ]
    traceback = _clean(_value(source, "traceback", ""))
    if traceback:
        lines.extend(["", "```text", traceback, "```"])
    lines.extend(["", "## Facts", ""])
    facts = _value(results, "facts", []) or []
    if facts:
        for fact in facts:
            lines.append("- {}".format(_clean(_value(fact, "text"))))
            evidence = _value(fact, "evidence", []) or []
            if evidence:
                lines.append(_evidence_lines(evidence))
    else:
        lines.append("_No facts were recorded._")

    lines.extend(["", "## Findings", ""])
    findings = _value(results, "findings", []) or []
    if findings:
        for finding in findings:
            lines.append("- **{}** — {}".format(_clean(_value(finding, "severity", "info")), _clean(_value(finding, "text"))))
            evidence = _value(finding, "evidence", []) or []
            if evidence:
                lines.append(_evidence_lines(evidence))
    else:
        lines.append("_No findings were recorded._")

    lines.extend(["", "## Ranked hypotheses", ""])
    hypotheses = _value(results, "hypotheses", []) or []
    if hypotheses:
        for index, hypothesis in enumerate(hypotheses, start=1):
            lines.append(
                "{}. **{:.0%}** — {}".format(
                    index,
                    float(_value(hypothesis, "score", 0.0)),
                    _clean(_value(hypothesis, "text")),
                )
            )
            rationale = _clean(_value(hypothesis, "rationale", ""))
            if rationale:
                lines.append("   - Rationale: {}".format(rationale))
            evidence = _value(hypothesis, "evidence", []) or []
            if evidence:
                lines.append(_evidence_lines(evidence))
    else:
        lines.append("_No hypotheses were generated._")

    lines.extend(["", "## Generated tests", ""])
    tests = _value(results, "generated_tests", []) or []
    if tests:
        for test in tests:
            lines.append("### `{}` — {}".format(_clean(_value(test, "path")), _clean(_value(test, "validation_status", "unknown"))))
            lines.append("")
            lines.append(_clean(_value(test, "purpose", "")))
            lines.extend(["", "```python", _clean(_value(test, "content", "")), "```"])
    else:
        lines.append("_No generated tests were recorded._")

    lines.extend(["", "## Execution results", ""])
    executions = _value(results, "execution_results", []) or []
    if executions:
        for execution in executions:
            lines.append(
                "- **{}** — exit code `{}`{}".format(
                    _clean(_value(execution, "status", "unknown")),
                    _value(execution, "exit_code", "n/a"),
                    " — {}".format(_clean(_value(execution, "reason"))) if _value(execution, "reason") else "",
                )
            )
            stdout = _clean(_value(execution, "stdout", ""))
            stderr = _clean(_value(execution, "stderr", ""))
            if stdout:
                lines.extend(["", "```text", stdout, "```"])
            if stderr:
                lines.extend(["", "```text", stderr, "```"])
    else:
        lines.append("_Tests have not been run._")

    verification = _value(results, "verification", {}) or {}
    lines.extend(["", "## Patch verification", ""])
    lines.append(
        "- **Status:** `{}`; **safe to apply:** `{}`; **file:** `{}`".format(
            _clean(_value(verification, "status", "not-run")),
            _value(verification, "safe_to_apply", False),
            _clean(_value(verification, "file_path", "n/a")),
        )
    )
    message = _clean(_value(verification, "message", ""))
    if message:
        lines.append("- {}".format(message))
    if _value(verification, "original_failure_reproduced") is not None:
        lines.append("- **Original failure reproduced:** `{}`".format(_value(verification, "original_failure_reproduced")))
    if _value(verification, "failure_disappeared") is not None:
        lines.append("- **Failure disappeared after proposed change:** `{}`".format(_value(verification, "failure_disappeared")))
    if _value(verification, "regressions_detected") is not None:
        lines.append("- **Regressions detected:** `{}`".format(_value(verification, "regressions_detected")))
    checks = _value(verification, "checks", []) or []
    for check in checks:
        lines.append("  - `{}`: **{}** — {}".format(_clean(_value(check, "name")), _clean(_value(check, "status")), _clean(_value(check, "message"))))
    diff = _clean(_value(verification, "diff", ""))
    if diff:
        lines.extend(["", "### Proposed diff", "", "```diff", diff, "```"])
    for label, key in (("Baseline execution", "baseline_execution"), ("Proposed execution", "patched_execution")):
        execution = _value(verification, key, None)
        if execution:
            lines.extend(
                [
                    "",
                    "### {}".format(label),
                    "",
                    "- Status: `{}`; exit code: `{}`".format(
                        _clean(_value(execution, "status", "unknown")),
                        _value(execution, "exit_code", "n/a"),
                    ),
                ]
            )
            reason = _clean(_value(execution, "reason", ""))
            if reason:
                lines.append("- {}".format(reason))
            for output_key in ("stdout", "stderr"):
                output = _clean(_value(execution, output_key, ""))
                if output:
                    lines.extend(["", "```text", output, "```"])
    lines.extend(["", "---", "Generated by Code-Aid's deterministic local analysis engines.", ""])
    return "\n".join(lines)


render_report = generate_markdown_report
