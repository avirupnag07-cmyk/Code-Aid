import ast
from pathlib import Path

import pytest

from app.engine.analyzer import analyze_project
from app.engine.ranking import rank_hypotheses
from app.engine.test_generation import generate_tests, validate_generated_tests
from app.engine.traceback_parser import parse_traceback


ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize(
    "sample_id, rule_id",
    [
        ("simple-reproducible-bug", "traceback-binary-operation"),
        ("unexpected-type-bug", "unchecked-attribute-access"),
        ("regression-after-fix-bug", "unchecked-mapping-lookup"),
    ],
)
def test_bundled_samples_produce_evidence_backed_findings(sample_id, rule_id, tmp_path):
    from app.engine.ingestion import SampleCatalog

    source = SampleCatalog(ROOT / "samples").ingest(sample_id, tmp_path / sample_id)
    info = parse_traceback(source.traceback)
    result = analyze_project(source.root, info, source.metadata)
    assert result.findings
    finding = next(item for item in result.findings if item["rule_id"] == rule_id)
    assert finding["evidence"][0]["file"]
    assert finding["evidence"][0]["line"]
    hypotheses = rank_hypotheses(info, result.findings, source.metadata)
    assert hypotheses
    assert 0 < hypotheses[0]["score"] <= 1


def test_generation_is_parseable_and_validated(tmp_path):
    from app.engine.ingestion import SampleCatalog

    source = SampleCatalog(ROOT / "samples").ingest("simple-reproducible-bug", tmp_path / "project")
    info = parse_traceback(source.traceback)
    generated = validate_generated_tests(generate_tests(info, source.metadata))
    assert generated[0]["validation_status"] == "valid"
    ast.parse(generated[0]["content"])
    assert "pytest.raises(TypeError)" in generated[0]["content"]


def test_generation_explicitly_skips_when_metadata_has_no_safe_call_spec():
    info = parse_traceback("ValueError: bad input")
    generated = generate_tests(info, {})
    assert "pytest.skip" in generated[0]["content"]
