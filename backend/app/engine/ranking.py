"""Deterministic hypothesis generation and ranking."""

from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

from .traceback_parser import TracebackInfo


def _exception_type(traceback_info: Any) -> str:
    if isinstance(traceback_info, TracebackInfo):
        return traceback_info.exception_type
    if isinstance(traceback_info, Mapping):
        return str(traceback_info.get("exception_type") or "")
    return str(getattr(traceback_info, "exception_type", "") or "")


def _message(traceback_info: Any) -> str:
    if isinstance(traceback_info, TracebackInfo):
        return traceback_info.message
    if isinstance(traceback_info, Mapping):
        return str(traceback_info.get("message") or "")
    return str(getattr(traceback_info, "message", "") or "")


def rank_hypotheses(
    traceback_info: Any,
    findings: Sequence[Mapping[str, Any]],
    metadata: Optional[Mapping[str, Any]] = None,
) -> List[Dict[str, Any]]:
    """Return stable, score-descending hypotheses without model/API calls."""

    exception_type = _exception_type(traceback_info)
    message = _message(traceback_info)
    candidates: List[Tuple[float, str, str, List[Dict[str, Any]]]] = []

    rule_scores = {
        "mixed-literal-operation": 0.98,
        "traceback-binary-operation": 0.92,
        "unchecked-mapping-lookup": 0.95,
        "unchecked-sequence-index": 0.95,
        "unchecked-attribute-access": 0.94,
        "unchecked-numeric-conversion": 0.93,
        "syntax-error": 0.97,
        "broad-exception": 0.55,
        "undefined-name": 0.94,
        "function-argument-count": 0.92,
        "inconsistent-return": 0.62,
    }
    rule_text = {
        "mixed-literal-operation": "The failure is caused by incompatible literal operand types in a binary operation.",
        "traceback-binary-operation": "The reported TypeError is caused by an operation receiving incompatible runtime operand types.",
        "unchecked-mapping-lookup": "The code assumes a mapping key exists, so a missing input key raises KeyError.",
        "unchecked-sequence-index": "The code indexes a sequence without proving that the requested position exists.",
        "unchecked-attribute-access": "The value reaching the attribute access has a runtime type without the required attribute.",
        "unchecked-numeric-conversion": "Unvalidated input reaches a numeric conversion and can raise ValueError.",
        "syntax-error": "The project cannot execute the affected module because its Python syntax is invalid.",
        "broad-exception": "Broad exception handling may be hiding the actual failure and allowing a regression to persist.",
        "undefined-name": "The failing path reads a name that is not visibly defined in the affected module.",
        "function-argument-count": "A local function call supplies an argument count outside the function signature.",
        "inconsistent-return": "The function exposes inconsistent return shapes across its paths.",
    }
    for finding in findings:
        rule_id = str(finding.get("rule_id") or "")
        if rule_id not in rule_text:
            continue
        evidence = list(finding.get("evidence") or [])
        candidates.append(
            (
                rule_scores[rule_id],
                rule_text[rule_id],
                "Static rule {} matched the supplied source evidence.".format(rule_id),
                evidence,
            )
        )

    generic_by_exception = {
        "TypeError": (
            "An input value has a different runtime type than the operation expects.",
            "Normalize or validate input types at the boundary before performing the reported operation.",
            0.76,
        ),
        "ValueError": (
            "An input value is syntactically present but invalid for the requested conversion or operation.",
            "Validate the value and return a clear domain error before conversion.",
            0.76,
        ),
        "AttributeError": (
            "An optional or unexpected value does not provide the attribute used by the failing code.",
            "Check the runtime value and its optional fields before accessing the attribute.",
            0.76,
        ),
        "KeyError": (
            "The input mapping does not contain a key that the code accesses directly.",
            "Use an explicit required-key check or a documented default for optional keys.",
            0.76,
        ),
        "IndexError": (
            "A sequence is empty or shorter than the index used by the failing code.",
            "Check sequence length and define the empty-input behavior.",
            0.76,
        ),
        "NameError": (
            "The failing path references a name that is not defined in the current scope.",
            "Check the name's definition and all conditional import or assignment paths.",
            0.72,
        ),
        "UnboundLocalError": (
            "A local variable is read before every control-flow path assigns it.",
            "Initialize the local or cover every assignment branch.",
            0.72,
        ),
        "ZeroDivisionError": (
            "A denominator can be zero on the reported input.",
            "Validate the denominator and define the zero case.",
            0.76,
        ),
    }
    if exception_type in generic_by_exception:
        text, rationale, score = generic_by_exception[exception_type]
        candidates.append((score, text, rationale, []))
    else:
        candidates.append(
            (
                0.60,
                "The reported {} needs a focused reproduction around the innermost traceback frame.".format(exception_type or "exception"),
                "No specialized static rule was conclusive for this exception type.",
                [],
            )
        )

    if metadata and str(metadata.get("category") or "").lower() in {"regression", "regression-after-fix"}:
        candidates.append(
            (
                0.68,
                "A recent fix changed an input or output contract without a regression test for this case.",
                "The bundled sample is marked as a regression-after-fix scenario.",
                [],
            )
        )

    # Deduplicate while keeping the strongest evidence for an identical idea.
    strongest: Dict[str, Tuple[float, str, str, List[Dict[str, Any]]]] = {}
    for item in candidates:
        current = strongest.get(item[1])
        if current is None or item[0] > current[0]:
            strongest[item[1]] = item
    ordered = sorted(strongest.values(), key=lambda item: (-item[0], item[1]))
    return [
        {
            "text": text,
            "score": round(score, 4),
            "rationale": rationale + ((" Message: " + message) if message and len(message) < 160 else ""),
            "evidence": evidence,
        }
        for score, text, rationale, evidence in ordered[:8]
    ]


# Alternative spelling retained for integrations that use a verb-first name.
rank = rank_hypotheses
