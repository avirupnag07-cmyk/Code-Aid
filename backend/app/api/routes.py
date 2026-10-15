"""FastAPI routes for the Code-Aid investigation workflow."""

import base64
import binascii
import json
from pathlib import Path
import shutil
from typing import Any, Dict, Iterable, List, Mapping, Optional, Tuple
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import JSONResponse, PlainTextResponse
from starlette.datastructures import UploadFile

from .. import __version__
from ..config import Settings
from ..db import InvestigationRepository
from ..engine.analyzer import analyze_project
from ..engine.ingestion import (
    IngestedProject,
    IngestionError,
    SampleCatalog,
    ingestion_limits_from_settings,
    ingest_zip,
)
from ..engine.patch_verifier import PatchVerificationError, verify_patch
from ..engine.ranking import rank_hypotheses
from ..engine.report import generate_markdown_report
from ..engine.runner import run_generated_tests
from ..engine.test_generation import generate_tests, validate_generated_tests
from ..engine.traceback_parser import TracebackParseError, parse_traceback
from ..schemas import (
    ErrorResponse,
    ExecutionResult,
    HealthResponse,
    Investigation,
    InvestigationResults,
    InvestigationSummary,
    PatchRequest,
    RunTestsRequest,
    SampleSummary,
    SourceInfo,
    VerificationResult,
)


def _dump(model: Any) -> Dict[str, Any]:
    if hasattr(model, "model_dump"):
        return model.model_dump()
    return model.dict()


def _parse_model(model_class: Any, payload: Mapping[str, Any]) -> Any:
    if hasattr(model_class, "model_validate"):
        return model_class.model_validate(dict(payload))
    return model_class.parse_obj(dict(payload))


def _first_text(data: Mapping[str, Any], *names: str) -> Optional[str]:
    for name in names:
        value = data.get(name)
        if value is None:
            continue
        if isinstance(value, str):
            return value
        return str(value)
    return None


def _response_record(record: Mapping[str, Any]) -> Dict[str, Any]:
    results = dict(record.get("results") or {})
    results.setdefault("facts", [])
    results.setdefault("findings", [])
    results.setdefault("hypotheses", [])
    results.setdefault("generated_tests", [])
    results.setdefault("execution_results", [])
    results.setdefault("verification", {"status": "not-run"})
    normalized_results = _dump(_parse_model(InvestigationResults, results))
    source = dict(record.get("source") or {})
    source.setdefault("source_type", record.get("source_type", "unknown"))
    source.setdefault("file_count", 0)
    source.setdefault("metadata", {})
    source.setdefault("traceback", "")
    source.setdefault("intake", {})
    normalized_source = _dump(_parse_model(SourceInfo, source))
    return {
        "id": record["id"],
        "title": record["title"],
        "status": record["status"],
        "source_type": record["source_type"],
        "sample_id": record.get("sample_id"),
        "created_at": record["created_at"],
        "updated_at": record["updated_at"],
        "finding_count": len(normalized_results["findings"]),
        "hypothesis_count": len(normalized_results["hypotheses"]),
        "source": normalized_source,
        "results": normalized_results,
    }


def _summary_record(record: Mapping[str, Any]) -> Dict[str, Any]:
    results = dict(record.get("results") or {})
    return {
        "id": record["id"],
        "title": record["title"],
        "status": record["status"],
        "source_type": record["source_type"],
        "sample_id": record.get("sample_id"),
        "created_at": record["created_at"],
        "updated_at": record["updated_at"],
        "finding_count": len(results.get("findings") or []),
        "hypothesis_count": len(results.get("hypotheses") or []),
    }


async def _create_payload(request: Request, settings: Settings) -> Tuple[Dict[str, Any], Optional[bytes], Optional[str]]:
    """Read JSON or multipart fields while enforcing an upload byte limit."""

    content_type = request.headers.get("content-type", "").lower()
    if content_type.startswith("multipart/form-data") or content_type.startswith("application/x-www-form-urlencoded"):
        form = await request.form()
        fields: Dict[str, Any] = {}
        upload: Optional[UploadFile] = None
        for key, value in form.multi_items():
            if isinstance(value, UploadFile) or value.__class__.__name__ == "UploadFile":
                if upload is not None:
                    raise HTTPException(status_code=400, detail="Only one ZIP upload is allowed")
                upload = value
            else:
                fields[key] = value
        if upload is None:
            return fields, None, None
        filename = upload.filename or "project.zip"
        if not filename.lower().endswith(".zip"):
            raise HTTPException(status_code=400, detail="Uploaded project must be a .zip archive")
        archive = await upload.read(settings.max_upload_bytes + 1)
        if len(archive) > settings.max_upload_bytes:
            raise HTTPException(status_code=413, detail="Uploaded archive exceeds the size limit")
        return fields, archive, filename
    try:
        body = await request.json()
    except (ValueError, json.JSONDecodeError):
        raise HTTPException(status_code=400, detail="Request must be JSON or multipart form data")
    if not isinstance(body, dict):
        raise HTTPException(status_code=422, detail="JSON request body must be an object")
    archive: Optional[bytes] = None
    filename: Optional[str] = None
    encoded = body.get("archive_base64") or body.get("zip_base64")
    if encoded is not None:
        if not isinstance(encoded, str):
            raise HTTPException(status_code=422, detail="archive_base64 must be a string")
        try:
            archive = base64.b64decode(encoded, validate=True)
        except (ValueError, binascii.Error) as exc:
            raise HTTPException(status_code=422, detail="archive_base64 is not valid base64") from exc
        if len(archive) > settings.max_upload_bytes:
            raise HTTPException(status_code=413, detail="Uploaded archive exceeds the size limit")
        filename = str(body.get("filename") or "project.zip")
        if not filename.lower().endswith(".zip"):
            raise HTTPException(status_code=400, detail="Uploaded project must be a .zip archive")
    return body, archive, filename


def _request_error(message: str, status_code: int = 400) -> HTTPException:
    return HTTPException(status_code=status_code, detail=message)


def create_router(settings: Settings, repository: InvestigationRepository, catalog: SampleCatalog) -> APIRouter:
    router = APIRouter()

    @router.get("/health", response_model=HealthResponse, tags=["system"])
    async def health() -> Dict[str, str]:
        return {
            "status": "ok",
            "service": "code-aid-backend",
            "version": __version__,
            "database": "sqlite",
        }

    @router.get("/samples", response_model=List[SampleSummary], tags=["samples"])
    async def list_samples() -> List[Dict[str, Any]]:
        return catalog.list()

    @router.get("/samples/{sample_id}", response_model=SampleSummary, tags=["samples"])
    async def get_sample(sample_id: str) -> Dict[str, Any]:
        try:
            return catalog.describe(sample_id)
        except IngestionError as exc:
            raise _request_error(str(exc), 404)

    @router.get("/investigations", response_model=List[InvestigationSummary], tags=["investigations"])
    async def list_investigations(
        limit: int = Query(100, ge=1, le=500), offset: int = Query(0, ge=0)
    ) -> List[Dict[str, Any]]:
        return [_summary_record(record) for record in repository.list(limit=limit, offset=offset)]

    @router.post("/investigations", response_model=Investigation, status_code=201, tags=["investigations"])
    async def create_investigation(request: Request) -> Dict[str, Any]:
        fields, archive, original_filename = await _create_payload(request, settings)
        sample_id = _first_text(fields, "sample_id", "sample")
        if sample_id is not None:
            sample_id = sample_id.strip()
        if sample_id and archive is not None:
            raise _request_error("Choose either sample_id or a ZIP upload, not both")
        if not sample_id and archive is None:
            raise _request_error("A safe sample_id or ZIP upload is required", 422)
        title = (_first_text(fields, "title", "name") or "").strip()
        if len(title) > 120:
            raise _request_error("title must be at most 120 characters", 422)
        traceback_override = _first_text(fields, "traceback", "traceback_text")
        investigation_id = str(uuid4())
        project_root = settings.storage_dir / investigation_id / "project"
        settings.storage_dir.mkdir(parents=True, exist_ok=True)
        try:
            if sample_id:
                try:
                    project = catalog.ingest(sample_id, project_root)
                except IngestionError as exc:
                    raise _request_error(str(exc), 404)
                if not title:
                    title = str(project.metadata.get("name") or sample_id)
            else:
                try:
                    project = ingest_zip(
                        archive or b"",
                        project_root,
                        limits=ingestion_limits_from_settings(settings),
                        original_filename=original_filename,
                    )
                except IngestionError as exc:
                    raise _request_error(str(exc), 400)
                if not title:
                    title = Path(original_filename or "uploaded-project.zip").stem or "Uploaded project"
            if traceback_override is not None:
                if len(traceback_override) > settings.max_traceback_chars:
                    raise _request_error("traceback exceeds the configured size limit", 413)
                project.traceback = traceback_override
            if not project.traceback.strip():
                raise _request_error("A traceback.txt file, metadata traceback, or traceback field is required", 422)
            try:
                traceback_info = parse_traceback(project.traceback, settings.max_traceback_chars)
            except TracebackParseError as exc:
                raise _request_error(str(exc), 422)
            analysis = analyze_project(
                project.root,
                traceback_info,
                metadata=project.metadata,
                max_source_file_bytes=settings.max_source_file_bytes,
            )
            hypotheses = rank_hypotheses(traceback_info, analysis.findings, project.metadata)
            generated_tests = validate_generated_tests(
                generate_tests(traceback_info, project.metadata, analysis.findings)
            )
            results = {
                "facts": analysis.facts,
                "findings": analysis.findings,
                "hypotheses": hypotheses,
                "generated_tests": generated_tests,
                "execution_results": [],
                "verification": {"status": "not-run", "safe_to_apply": False, "checks": []},
            }
            source = {
                "source_type": project.source_type,
                "sample_id": project.sample_id,
                "original_filename": project.original_filename,
                "file_count": project.file_count,
                "traceback": project.traceback,
                "metadata": project.metadata,
                "intake": {
                    key: value
                    for key in (
                        "bug_description",
                        "reproduction_steps",
                        "expected_behavior",
                        "actual_behavior",
                        "environment",
                    )
                    if (value := _first_text(fields, key)) is not None and value.strip()
                },
            }
            record = repository.create(
                investigation_id,
                title or "Code-Aid investigation",
                "analyzed",
                project.source_type,
                project.sample_id,
                source,
                results,
                project.root,
            )
            return _response_record(record)
        except HTTPException:
            shutil.rmtree(str(settings.storage_dir / investigation_id), ignore_errors=True)
            raise
        except Exception:
            shutil.rmtree(str(settings.storage_dir / investigation_id), ignore_errors=True)
            raise

    @router.get("/investigations/{investigation_id}", response_model=Investigation, tags=["investigations"])
    async def get_investigation(investigation_id: str) -> Dict[str, Any]:
        record = repository.get(investigation_id)
        if record is None:
            raise _request_error("Investigation not found", 404)
        return _response_record(record)

    @router.delete("/investigations/{investigation_id}", tags=["investigations"])
    async def delete_investigation(investigation_id: str) -> Dict[str, Any]:
        record = repository.delete(investigation_id)
        if record is None:
            raise _request_error("Investigation not found", 404)
        storage_path = Path(str(record.get("storage_path") or ""))
        investigation_dir = storage_path.parent
        try:
            investigation_dir.resolve().relative_to(settings.storage_dir.resolve())
            shutil.rmtree(str(investigation_dir), ignore_errors=True)
        except ValueError:
            pass
        return {"deleted": True, "id": investigation_id}

    @router.post("/investigations/{investigation_id}/run-tests", tags=["execution"])
    async def run_tests(investigation_id: str, request: Request) -> Dict[str, Any]:
        record = repository.get(investigation_id)
        if record is None:
            raise _request_error("Investigation not found", 404)
        timeout = settings.run_timeout_seconds
        body_bytes = await request.body()
        if body_bytes.strip():
            try:
                body = json.loads(body_bytes.decode("utf-8"))
                parsed = _parse_model(RunTestsRequest, body)
                timeout = parsed.timeout_seconds or timeout
            except (UnicodeDecodeError, ValueError, TypeError) as exc:
                raise _request_error("Invalid run-tests JSON body", 422) from exc
        results = dict(record.get("results") or {})
        execution = run_generated_tests(
            Path(str(record["storage_path"])),
            results.get("generated_tests") or [],
            timeout_seconds=timeout,
            docker_image=settings.docker_image,
        )
        executions = list(results.get("execution_results") or [])
        executions.append(execution)
        results["execution_results"] = executions
        next_status = "tests-{}".format(execution.get("status", "completed"))
        updated = repository.update(investigation_id, status=next_status, results=results)
        response = _response_record(updated or record)
        response["execution_result"] = execution
        return response

    @router.post("/investigations/{investigation_id}/verify", tags=["verification"])
    async def verify_investigation_patch(investigation_id: str, request: Request) -> Dict[str, Any]:
        record = repository.get(investigation_id)
        if record is None:
            raise _request_error("Investigation not found", 404)
        try:
            payload = await request.json()
        except (ValueError, json.JSONDecodeError) as exc:
            raise _request_error("Patch verification requires a JSON body", 422) from exc
        if not isinstance(payload, dict):
            raise _request_error("Patch verification body must be an object", 422)
        if "path" in payload and "file_path" not in payload:
            payload["file_path"] = payload.pop("path")
        try:
            patch = _parse_model(PatchRequest, payload)
        except ValueError as exc:
            raise _request_error(str(exc), 422) from exc
        try:
            verification = verify_patch(
                Path(str(record["storage_path"])),
                patch.file_path,
                patch.content,
                max_bytes=settings.max_source_file_bytes,
            )
        except PatchVerificationError as exc:
            raise _request_error(str(exc), 400) from exc
        results = dict(record.get("results") or {})
        results["verification"] = verification
        updated = repository.update(investigation_id, status="patch-verified", results=results)
        response = _response_record(updated or record)
        response["verification"] = verification
        response["investigation"] = response.copy()
        return response

    @router.get("/investigations/{investigation_id}/report", tags=["reports"])
    async def download_report(investigation_id: str) -> PlainTextResponse:
        record = repository.get(investigation_id)
        if record is None:
            raise _request_error("Investigation not found", 404)
        markdown = generate_markdown_report(_response_record(record))
        headers = {"Content-Disposition": 'attachment; filename="code-aid-{}.md"'.format(investigation_id)}
        return PlainTextResponse(markdown, media_type="text/markdown; charset=utf-8", headers=headers)

    return router
