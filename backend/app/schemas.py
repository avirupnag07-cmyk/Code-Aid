"""Pydantic models shared by the API and engine boundaries."""

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


class Model(BaseModel):
    """Base model that accepts only the documented fields."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)


class Evidence(Model):
    file: Optional[str] = None
    line: Optional[int] = None
    end_line: Optional[int] = None
    snippet: Optional[str] = None
    reason: str = ""


class Fact(Model):
    text: str
    evidence: List[Evidence] = Field(default_factory=list)


class Finding(Model):
    text: str
    severity: str = "info"
    rule_id: str = ""
    evidence: List[Evidence] = Field(default_factory=list)


class LanguageDiagnostic(Model):
    """Normalized output from a language parser/compiler check."""

    language: str
    path: str
    line: Optional[int] = None
    column: Optional[int] = None
    severity: str = "error"
    message: str
    tool: str
    code: str = ""
    source: str = "adapter"


class LanguageAnalysis(Model):
    language: Optional[str] = None
    detected_languages: List[str] = Field(default_factory=list)
    diagnostics: List[LanguageDiagnostic] = Field(default_factory=list)
    analyzed_files: List[str] = Field(default_factory=list)
    toolchains: Dict[str, Dict[str, Any]] = Field(default_factory=dict)


class Hypothesis(Model):
    text: str
    score: float = Field(ge=0.0, le=1.0)
    rationale: str = ""
    evidence: List[Evidence] = Field(default_factory=list)


class GeneratedTest(Model):
    path: str
    content: str
    purpose: str
    validation_status: str = "not-checked"
    validation_message: str = ""
    test_mode: str = "exception-reproduction"


class ExecutionResult(Model):
    status: str
    exit_code: Optional[int] = None
    stdout: str = ""
    stderr: str = ""
    duration_ms: Optional[int] = None
    reason: str = ""
    command: List[str] = Field(default_factory=list)
    started_at: Optional[str] = None
    finished_at: Optional[str] = None


class VerificationCheck(Model):
    name: str
    status: str
    message: str = ""
    evidence: List[Evidence] = Field(default_factory=list)


class VerificationResult(Model):
    status: str = "not-run"
    file_path: Optional[str] = None
    changed: bool = False
    safe_to_apply: bool = False
    syntax_valid: Optional[bool] = None
    diff: str = ""
    message: str = ""
    checks: List[VerificationCheck] = Field(default_factory=list)
    baseline_execution: Optional[ExecutionResult] = None
    patched_execution: Optional[ExecutionResult] = None
    original_failure_reproduced: Optional[bool] = None
    failure_disappeared: Optional[bool] = None
    regressions_detected: Optional[bool] = None


class InvestigationResults(Model):
    """Analysis output deliberately keeps facts/findings/hypotheses separate."""

    facts: List[Fact] = Field(default_factory=list)
    findings: List[Finding] = Field(default_factory=list)
    hypotheses: List[Hypothesis] = Field(default_factory=list)
    generated_tests: List[GeneratedTest] = Field(default_factory=list)
    execution_results: List[ExecutionResult] = Field(default_factory=list)
    verification: VerificationResult = Field(default_factory=VerificationResult)
    language: Optional[str] = None
    detected_languages: List[str] = Field(default_factory=list)
    diagnostics: List[LanguageDiagnostic] = Field(default_factory=list)
    language_diagnostics: List[LanguageDiagnostic] = Field(default_factory=list)
    language_analysis: LanguageAnalysis = Field(default_factory=LanguageAnalysis)


class SourceFile(Model):
    path: str
    kind: str = "source"
    size: int = 0


class SourceInfo(Model):
    source_type: str
    sample_id: Optional[str] = None
    original_filename: Optional[str] = None
    file_count: int = 0
    traceback: str = ""
    metadata: Dict[str, Any] = Field(default_factory=dict)
    intake: Dict[str, str] = Field(default_factory=dict)
    files: List[SourceFile] = Field(default_factory=list)
    language: Optional[str] = None
    detected_languages: List[str] = Field(default_factory=list)


class InvestigationSummary(Model):
    id: str
    title: str
    status: str
    source_type: str
    sample_id: Optional[str] = None
    created_at: str
    updated_at: str
    finding_count: int = 0
    hypothesis_count: int = 0


class Investigation(InvestigationSummary):
    source: SourceInfo
    results: InvestigationResults


class SampleSummary(Model):
    id: str
    name: str
    description: str
    category: str = ""
    exception_type: str = ""
    traceback: str = ""
    file_count: int = 0
    metadata: Dict[str, Any] = Field(default_factory=dict)


class HealthResponse(Model):
    status: str
    service: str
    version: str
    database: str


class PatchRequest(Model):
    file_path: str = Field(min_length=1, max_length=400)
    content: str = Field(max_length=512 * 1024)

    @field_validator("file_path")
    @classmethod
    def validate_file_path(cls, value: str) -> str:
        if "\x00" in value:
            raise ValueError("file_path cannot contain NUL bytes")
        return value


class RunTestsRequest(Model):
    timeout_seconds: Optional[int] = Field(default=None, ge=1, le=300)


class ErrorResponse(Model):
    detail: str
    code: str = "invalid_request"
