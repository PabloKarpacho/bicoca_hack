import hashlib
from pathlib import Path
from urllib.parse import quote

from botocore.exceptions import ClientError
from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    Form,
    HTTPException,
    Query,
    Request,
    UploadFile,
    status,
)
from fastapi.responses import Response
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from app.config.enums.document_status import DocumentProcessingStatus
from app.config.enums.processing_stage import ProcessingStage
from app.config.enums.search_strategy import SearchStrategy
from app.models.candidate_search import CandidateSearchFilters, CandidateSearchResult
from app.models.candidate_vector import CandidateVectorIndexRunResponse
from app.models.candidate_vector import (
    CandidateVectorDebugSearchRequest,
    CandidateVectorDebugSearchResponse,
)
from app.models.cv import (
    CandidateUpsertPayload,
    DocumentListResponse,
    DocumentPipelineStatusResponse,
    DocumentStatusResponse,
    ErrorResponse,
    PipelineStageStatusResponse,
    UploadDocumentResponse,
)
from app.models.entity_extraction import (
    CandidateEntitiesResponse,
    EntityExtractionRunResponse,
)
from app.models.job_search import (
    JobSearchPreparationRequest,
)
from app.models.rag import DeleteFileResponse
from app.models.skill_normalization import HHSkillSuggestion
from app.models.work_normalization import HHWorkSuggestion
from app.service.cv.background_ingestion import ResumeBackgroundIngestionService
from app.service.cv.entity_extraction.graph import EntityExtractionGraphError
from app.service.cv.entity_extraction.service import CandidateEntityExtractionService
from app.service.job_search.graph import JobSearchPreparationError
from app.service.job_search.service import JobSearchPreparationService
from app.service.search.candidate_rule_search import CandidateRuleSearchService
from app.service.search.candidate_match_scoring import calculate_candidate_match_score
from app.service.search.candidate_vector_indexing import (
    CandidateVectorIndexingError,
    CandidateVectorIndexingService,
)
from app.service.search.candidate_vector_search import (
    CandidateVectorSearchError,
    CandidateVectorSearchService,
)
from app.service.skills.hh_skill_normalizer import HHSkillNormalizerService
from app.service.work.hh_work_normalizer import HHWorkNormalizerService
from database.postgres.crud.cv import (
    CandidateDocumentRepository,
    CandidateRepository,
    DocumentProcessingRunRepository,
)
from database.postgres.db import get_db_session

router = APIRouter(prefix="/rag")

SUPPORTED_FILE_TYPES = {".pdf", ".docx"}


def build_document_download_path(document_id: str) -> str:
    """Return the public backend path used to download a stored resume."""
    return f"/rag/file/{document_id}/download"


def build_status_response(document) -> DocumentStatusResponse:
    """Build an API response model for the current document processing state.

    Args:
        document: ORM entity with document metadata, candidate data, and text relation.

    Returns:
        DocumentStatusResponse: Serialized document status payload.
    """
    return DocumentStatusResponse(
        document_id=document.document_id,
        candidate_id=document.candidate_id,
        original_filename=document.original_filename,
        file_extension=document.file_extension,
        content_type=document.content_type,
        size_bytes=document.size_bytes,
        checksum_sha256=document.checksum_sha256,
        processing_status=document.processing_status,
        indexing_status=document.indexing_status,
        extractor_name=document.extractor_name,
        extracted_char_count=document.extracted_char_count,
        text_available=document.text is not None,
        error_message=document.error_message,
        created_at=document.created_at,
        updated_at=document.updated_at,
        candidate=document.candidate,
    )


async def get_or_create_candidate(
    *,
    candidates: CandidateRepository,
    session: AsyncSession,
    payload: CandidateUpsertPayload,
):
    """Resolve the target candidate for an uploaded CV or create a new one.

    Args:
        candidates: Repository used to search and persist candidate records.
        session: Active database session for flush operations.
        payload: Candidate identifiers and optional profile fields from the request.

    Returns:
        Candidate: Existing or newly created candidate entity.
    """
    candidate = None
    if payload.candidate_id:
        candidate = await candidates.get_by_id(payload.candidate_id)
    if candidate is None and payload.external_id:
        candidate = await candidates.get_by_external_id(payload.external_id)
    if candidate is None and payload.email:
        candidate = await candidates.get_by_email(str(payload.email))

    if candidate is None:
        candidate = await candidates.create(
            external_id=payload.external_id,
            full_name=payload.full_name,
            email=str(payload.email) if payload.email else None,
        )
        await session.flush()
        return candidate

    if payload.full_name is not None or payload.email is not None:
        candidate = await candidates.update(
            candidate,
            full_name=payload.full_name,
            email=str(payload.email) if payload.email else None,
        )
    return candidate


def merge_hybrid_results(
    *,
    original_filters: CandidateSearchFilters,
    rule_result: CandidateSearchResult,
    vector_result: CandidateSearchResult,
) -> CandidateSearchResult:
    """Merge rule-based evidence into vector-ranked results.

    Hybrid search uses PostgreSQL as the first-stage shortlist generator and Qdrant as the
    second-stage semantic reranker. The vector stage preserves ranking, while the rule
    stage contributes structured evidence such as matched skills and languages.

    After merging that evidence, we recalculate the recruiter-facing match percentage so
    the final item reflects both semantic similarity and structured overlap.
    """
    rule_items_by_candidate = {
        item.candidate_id: item for item in rule_result.items
    }
    merged_items = []
    for item in vector_result.items:
        rule_item = rule_items_by_candidate.get(item.candidate_id)
        if rule_item is not None:
            if item.match_metadata is None:
                item.match_metadata = rule_item.match_metadata
            match_score_percent, match_score_breakdown = calculate_candidate_match_score(
                filters=original_filters,
                current_title_normalized=item.current_title_normalized,
                total_experience_months=item.total_experience_months,
                match_metadata=item.match_metadata,
                vector_semantic_score=item.score,
            )
            item.match_score_percent = match_score_percent
            item.match_score_breakdown = match_score_breakdown
        merged_items.append(item)
    return CandidateSearchResult(
        total=vector_result.total,
        items=merged_items,
        applied_filters=original_filters,
    )


async def enrich_search_results_with_resume_links(
    *,
    session: AsyncSession,
    result: CandidateSearchResult,
) -> CandidateSearchResult:
    """Attach backend download URLs to search results when a stored file exists."""
    if not result.items:
        return result

    document_ids = list(dict.fromkeys(item.document_id for item in result.items))
    documents = await CandidateDocumentRepository(session).list_by_ids(document_ids)
    documents_by_id = {document.document_id: document for document in documents}

    for item in result.items:
        document = documents_by_id.get(item.document_id)
        if (
            document is None
            or not document.storage_bucket
            or not document.storage_key
        ):
            continue
        item.resume_download_url = build_document_download_path(item.document_id)
    return result


def build_stage_status(run, stage: ProcessingStage) -> PipelineStageStatusResponse | None:
    """Convert one processing run row into an API stage status payload."""
    if run is None:
        return None
    return PipelineStageStatusResponse(
        stage=stage.value,
        status=run.status,
        pipeline_version=run.pipeline_version,
        model_version=run.model_version,
        extraction_confidence=run.extraction_confidence,
        error_message=run.error_message,
        started_at=run.started_at,
        completed_at=run.completed_at,
    )


def resolve_current_stage(
    *,
    document,
    raw_text_run,
    entity_run,
    vector_run,
) -> str:
    """Resolve the most relevant current pipeline stage for frontend polling."""
    if document.processing_status == DocumentProcessingStatus.FAILED.value:
        if vector_run and vector_run.status == "failed":
            return ProcessingStage.VECTOR_INDEXING.value
        if entity_run and entity_run.status == "failed":
            return ProcessingStage.ENTITY_EXTRACTION.value
        if raw_text_run and raw_text_run.status == "failed":
            return ProcessingStage.RAW_TEXT_EXTRACTION.value
        return "failed"
    if vector_run and vector_run.status == "started":
        return ProcessingStage.VECTOR_INDEXING.value
    if entity_run and entity_run.status == "started":
        return ProcessingStage.ENTITY_EXTRACTION.value
    if raw_text_run and raw_text_run.status == "started":
        return ProcessingStage.RAW_TEXT_EXTRACTION.value
    if document.processing_status == DocumentProcessingStatus.READY.value:
        return "completed"
    if document.processing_status == DocumentProcessingStatus.STORED.value:
        return "queued"
    return document.processing_status


def build_pipeline_status_response(
    *,
    document,
    raw_text_run,
    entity_run,
    vector_run,
) -> DocumentPipelineStatusResponse:
    """Build a polling-friendly pipeline status response for one document."""
    return DocumentPipelineStatusResponse(
        document_id=document.document_id,
        candidate_id=document.candidate_id,
        processing_status=document.processing_status,
        indexing_status=document.indexing_status,
        current_stage=resolve_current_stage(
            document=document,
            raw_text_run=raw_text_run,
            entity_run=entity_run,
            vector_run=vector_run,
        ),
        is_terminal=document.processing_status
        in {
            DocumentProcessingStatus.READY.value,
            DocumentProcessingStatus.FAILED.value,
        },
        text_available=document.text is not None,
        storage_available=bool(document.storage_key),
        error_message=document.error_message,
        raw_text_extraction=build_stage_status(
            raw_text_run,
            ProcessingStage.RAW_TEXT_EXTRACTION,
        ),
        entity_extraction=build_stage_status(
            entity_run,
            ProcessingStage.ENTITY_EXTRACTION,
        ),
        vector_indexing=build_stage_status(
            vector_run,
            ProcessingStage.VECTOR_INDEXING,
        ),
        updated_at=document.updated_at,
    )


@router.post(
    "/ingest_file",
    tags=["Upload and Process"],
    status_code=status.HTTP_202_ACCEPTED,
    response_model=UploadDocumentResponse,
    responses={
        409: {"model": ErrorResponse},
        415: {"model": ErrorResponse},
        422: {"model": ErrorResponse},
        500: {"model": ErrorResponse},
    },
)
async def ingest_file(
    request: Request,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    candidate_id: str | None = Form(None),
    candidate_external_id: str | None = Form(None),
    candidate_full_name: str | None = Form(None),
    candidate_email: str | None = Form(None),
    session: AsyncSession = Depends(get_db_session),
) -> UploadDocumentResponse:
    """Upload a CV, store the original file, and schedule background processing.

    Args:
        request: FastAPI request with initialized application services.
        file: Uploaded PDF or DOCX file.
        candidate_id: Optional internal candidate identifier.
        candidate_external_id: Optional external candidate identifier.
        candidate_full_name: Optional candidate full name to create or update.
        candidate_email: Optional candidate email to create or update.
        session: Active database session.

    Returns:
        UploadDocumentResponse: Accepted document identifier, candidate identifier,
        checksum, and polling URL for background pipeline status.
    """
    if not file.filename:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Filename is required",
        )

    payload = CandidateUpsertPayload(
        candidate_id=candidate_id,
        external_id=candidate_external_id,
        full_name=candidate_full_name,
        email=candidate_email,
    )
    file_bytes = await file.read()
    file_extension = Path(file.filename).suffix.lower()
    if file_extension not in SUPPORTED_FILE_TYPES:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=(
                "Unsupported file type: {ext}. Supported types are: {supported}"
            ).format(
                ext=file_extension.lstrip(".") or "unknown",
                supported=", ".join(
                    sorted(ext.lstrip(".") for ext in SUPPORTED_FILE_TYPES)
                ),
            ),
        )
    if not file_bytes:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Uploaded file is empty",
        )

    try:
        candidates = CandidateRepository(session)
        documents = CandidateDocumentRepository(session)

        candidate = await get_or_create_candidate(
            candidates=candidates,
            session=session,
            payload=payload,
        )
        checksum_sha256 = hashlib.sha256(file_bytes).hexdigest()
        duplicate = await documents.get_by_candidate_and_checksum(
            candidate.candidate_id,
            checksum_sha256,
        )
        if duplicate is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Duplicate document detected. Existing document_id={duplicate.document_id}",
            )

        document = await documents.create(
            candidate_id=candidate.candidate_id,
            original_filename=file.filename,
            file_extension=file_extension.lstrip("."),
            content_type=file.content_type,
            size_bytes=len(file_bytes),
            checksum_sha256=checksum_sha256,
            processing_status=DocumentProcessingStatus.UPLOADED,
        )
        await session.commit()

        object_key = await request.app.state.cv_storage.upload_original(
            document_id=document.document_id,
            filename=file.filename,
            content_type=file.content_type,
            data=file_bytes,
        )
        await documents.update_storage(
            document,
            bucket=request.app.state.cv_storage.bucket_name,
            key=object_key,
            processing_status=DocumentProcessingStatus.STORED,
        )
        await session.commit()
    except HTTPException:
        await session.rollback()
        raise
    except Exception as exc:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Could not parse uploaded file: {exc}",
        ) from exc

    logger.info(
        "RAG file uploaded and background processing scheduled: file_id={file_id}, filename={filename}",
        file_id=document.document_id,
        filename=file.filename,
    )

    background_service = ResumeBackgroundIngestionService(
        sessionmaker=request.app.state.db_sessionmaker,
        cv_storage=request.app.state.cv_storage,
        qdrant=getattr(request.app.state, "qdrant", None),
    )
    background_tasks.add_task(
        background_service.run,
        document_id=document.document_id,
        file_bytes=file_bytes,
        filename=file.filename,
    )

    return UploadDocumentResponse(
        document_id=document.document_id,
        candidate_id=document.candidate_id,
        status=document.processing_status,
        checksum_sha256=document.checksum_sha256,
        pipeline_status_url=f"/rag/file/{document.document_id}/pipeline-status",
    )


@router.get(
    "/files",
    response_model=DocumentListResponse,
)
async def list_files(
    session: AsyncSession = Depends(get_db_session),
) -> DocumentListResponse:
    """Return all uploaded documents ordered from newest to oldest."""
    documents = await CandidateDocumentRepository(session).list_all()
    return DocumentListResponse(
        total=len(documents),
        items=[build_status_response(document) for document in documents],
    )


@router.get(
    "/file/{file_id}/download",
    responses={404: {"model": ErrorResponse}},
)
async def download_file(
    request: Request,
    file_id: str,
    session: AsyncSession = Depends(get_db_session),
) -> Response:
    """Download a stored resume through the backend without exposing MinIO publicly."""
    documents = CandidateDocumentRepository(session)
    document = await documents.get_plain_by_id(file_id)
    if document is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found",
        )
    if not document.storage_key:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Stored resume file is not available",
        )

    bucket_name = (
        document.storage_bucket or request.app.state.cv_storage.bucket_name
    )
    try:
        file_bytes, content_type = await request.app.state.s3.download_bytes(
            key=document.storage_key,
            bucket_name=bucket_name,
        )
    except ClientError as exc:
        error_code = exc.response.get("Error", {}).get("Code")
        if error_code in {"NoSuchKey", "NoSuchBucket", "404"}:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Stored resume file is not available",
            ) from exc
        logger.exception(
            "Failed to download resume from storage for document_id={document_id}",
            document_id=file_id,
        )
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Resume storage is temporarily unavailable",
        ) from exc
    except Exception as exc:
        logger.exception(
            "Unexpected storage error while downloading resume for document_id={document_id}",
            document_id=file_id,
        )
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Resume storage is temporarily unavailable",
        ) from exc

    safe_filename = document.original_filename.replace('"', "")
    encoded_filename = quote(document.original_filename)
    headers = {
        "Content-Disposition": (
            f"inline; filename=\"{safe_filename}\"; "
            f"filename*=UTF-8''{encoded_filename}"
        )
    }
    return Response(
        content=file_bytes,
        media_type=content_type or document.content_type or "application/octet-stream",
        headers=headers,
    )


@router.get(
    "/file/{file_id}",
    response_model=DocumentStatusResponse,
    responses={404: {"model": ErrorResponse}},
)
async def get_file_status(
    file_id: str,
    session: AsyncSession = Depends(get_db_session),
) -> DocumentStatusResponse:
    """Return the current processing status and metadata for a stored file.

    Args:
        file_id: Identifier of the persisted document to inspect.
        session: Active database session.

    Returns:
        DocumentStatusResponse: Current persisted state of the requested document.
    """
    documents = CandidateDocumentRepository(session)
    document = await documents.get_by_id(file_id)
    if document is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found",
        )
    return build_status_response(document)


@router.get(
    "/file/{file_id}/pipeline-status",
    tags=["Upload and Process"],
    response_model=DocumentPipelineStatusResponse,
    responses={404: {"model": ErrorResponse}},
)
async def get_file_pipeline_status(
    file_id: str,
    session: AsyncSession = Depends(get_db_session),
) -> DocumentPipelineStatusResponse:
    """Return detailed pipeline progress for frontend polling.

    Args:
        file_id: Identifier of the persisted document to inspect.
        session: Active database session.

    Returns:
        DocumentPipelineStatusResponse: Coarse document state and per-stage run statuses.
    """
    documents = CandidateDocumentRepository(session)
    runs = DocumentProcessingRunRepository(session)
    document = await documents.get_by_id(file_id)
    if document is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found",
        )
    raw_text_run = await runs.get_by_document_and_stage(
        file_id,
        ProcessingStage.RAW_TEXT_EXTRACTION,
    )
    entity_run = await runs.get_by_document_and_stage(
        file_id,
        ProcessingStage.ENTITY_EXTRACTION,
    )
    vector_run = await runs.get_by_document_and_stage(
        file_id,
        ProcessingStage.VECTOR_INDEXING,
    )
    return build_pipeline_status_response(
        document=document,
        raw_text_run=raw_text_run,
        entity_run=entity_run,
        vector_run=vector_run,
    )


@router.post(
    "/file/{file_id}/index-vectors",
    tags=["Upload and Process"],
    response_model=CandidateVectorIndexRunResponse,
    responses={
        404: {"model": ErrorResponse},
        409: {"model": ErrorResponse},
        503: {"model": ErrorResponse},
    },
)
async def index_file_vectors(
    request: Request,
    file_id: str,
    session: AsyncSession = Depends(get_db_session),
) -> CandidateVectorIndexRunResponse:
    """Persist candidate chunks and index them in Qdrant for one CV document.

    Args:
        request: FastAPI request with initialized application services.
        file_id: Identifier of the document to build and index chunks for.
        session: Active database session.

    Returns:
        CandidateVectorIndexRunResponse: Vector indexing run result for the document.
    """
    qdrant = getattr(request.app.state, "qdrant", None)
    service = CandidateVectorIndexingService(
        session=session,
        qdrant=qdrant,
    )
    try:
        return await service.index_document(file_id)
    except CandidateVectorIndexingError as exc:
        if str(exc) == "Document not found":
            status_code = status.HTTP_404_NOT_FOUND
        elif str(exc) == "Qdrant is not configured":
            status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        else:
            status_code = status.HTTP_409_CONFLICT
        raise HTTPException(status_code=status_code, detail=str(exc)) from exc


@router.post(
    "/search/vector-debug",
    tags=["Search"],
    response_model=CandidateVectorDebugSearchResponse,
    responses={422: {"model": ErrorResponse}},
)
async def debug_vector_search(
    request: Request,
    payload: CandidateVectorDebugSearchRequest,
    session: AsyncSession = Depends(get_db_session),
) -> CandidateVectorDebugSearchResponse:
    """Run raw vector search for experiments and return chunk-level hits.

    Args:
        request: FastAPI request with initialized application services.
        payload: Plain-text semantic query for one raw vector lookup.
        session: Active database session.

    Returns:
        CandidateVectorDebugSearchResponse: Raw query embedding metadata and
        chunk-level Qdrant hits with scores and payloads.
    """
    service = CandidateVectorSearchService(
        session=session,
        qdrant=getattr(request.app.state, "qdrant", None),
    )
    try:
        return await service.debug_search(payload.query_text)
    except CandidateVectorSearchError as exc:
        status_code = (
            status.HTTP_503_SERVICE_UNAVAILABLE
            if str(exc) == "Qdrant is not configured"
            else status.HTTP_409_CONFLICT
        )
        raise HTTPException(status_code=status_code, detail=str(exc)) from exc


@router.post(
    "/search",
    tags=["Search"],
    response_model=CandidateSearchResult,
    responses={422: {"model": ErrorResponse}},
)
async def search_candidates(
    request: Request,
    filters: CandidateSearchFilters,
    search_strategy: SearchStrategy = Query(default=SearchStrategy.RULE_BASED),
    session: AsyncSession = Depends(get_db_session),
) -> CandidateSearchResult:
    """Search candidates using the selected shortlist strategy.

    Args:
        filters: Typed filter object for profile, skill, language, experience,
            education, certification, pagination, and ordering constraints.
        search_strategy: Search strategy selector. `hybrid` runs PostgreSQL
            rule-based shortlist first and then vector reranking only across
            shortlisted candidate ids.
        session: Active database session.

    Returns:
        CandidateSearchResult: Paginated shortlist of matching candidates with
        applied filters and lightweight match metadata.
    """
    logger.info(
        "RAG search requested with strategy={strategy}",
        strategy=search_strategy.value,
    )
    qdrant = getattr(request.app.state, "qdrant", None)
    if search_strategy == SearchStrategy.RULE_BASED:
        service = CandidateRuleSearchService(session)
        result = await service.search(filters)
        return await enrich_search_results_with_resume_links(
            session=session,
            result=result,
        )
    if search_strategy == SearchStrategy.VECTOR:
        service = CandidateVectorSearchService(
            session=session,
            qdrant=qdrant,
        )
        try:
            result = await service.search(filters)
        except CandidateVectorSearchError as exc:
            status_code = (
                status.HTTP_503_SERVICE_UNAVAILABLE
                if str(exc) == "Qdrant is not configured"
                else status.HTTP_409_CONFLICT
            )
            raise HTTPException(status_code=status_code, detail=str(exc)) from exc
        return await enrich_search_results_with_resume_links(
            session=session,
            result=result,
        )
    if search_strategy == SearchStrategy.HYBRID:
        rule_service = CandidateRuleSearchService(session)
        rule_result = await rule_service.search(filters)
        if rule_result.total == 0:
            return await enrich_search_results_with_resume_links(
                session=session,
                result=rule_result,
            )
        shortlist_candidate_ids = list(
            dict.fromkeys(item.candidate_id for item in rule_result.items)
        )
        vector_filters = filters.model_copy(
            update={
                "candidate_ids": shortlist_candidate_ids,
                "limit": max(filters.limit, len(shortlist_candidate_ids)),
                "offset": 0,
            }
        )
        vector_service = CandidateVectorSearchService(
            session=session,
            qdrant=qdrant,
        )
        try:
            vector_result = await vector_service.search(vector_filters)
        except CandidateVectorSearchError as exc:
            if (
                str(exc)
                == "query_text or semantic filters are required for vector search"
            ):
                logger.info(
                    "Hybrid search fallback to rule-based result because no vector query could be built"
                )
                return await enrich_search_results_with_resume_links(
                    session=session,
                    result=rule_result,
                )
            status_code = (
                status.HTTP_503_SERVICE_UNAVAILABLE
                if str(exc) == "Qdrant is not configured"
                else status.HTTP_409_CONFLICT
            )
            raise HTTPException(status_code=status_code, detail=str(exc)) from exc
        if vector_result.total == 0:
            return await enrich_search_results_with_resume_links(
                session=session,
                result=rule_result,
            )
        merged_result = merge_hybrid_results(
            original_filters=filters,
            rule_result=rule_result,
            vector_result=vector_result,
        )
        return await enrich_search_results_with_resume_links(
            session=session,
            result=merged_result,
        )
    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail=f"Unsupported search strategy: {search_strategy.value}",
    )


@router.get(
    "/skills/autocomplete",
    tags=["Search"],
    response_model=list[HHSkillSuggestion],
)
async def autocomplete_skills(
    q: str = Query(min_length=1),
) -> list[HHSkillSuggestion]:
    """Return HH-based skill autosuggest options for frontend autocomplete."""
    service = HHSkillNormalizerService()
    return await service.suggest_skills(q)


@router.get(
    "/professions/autocomplete",
    tags=["Search"],
    response_model=list[HHWorkSuggestion],
)
async def autocomplete_professions(
    q: str = Query(min_length=1),
) -> list[HHWorkSuggestion]:
    """Return HH-based profession autosuggest options for frontend autocomplete."""
    service = HHWorkNormalizerService()
    return await service.suggest_works(q)


@router.post(
    "/jobs/prepare",
    tags=["Search"],
    response_model=CandidateSearchFilters,
    responses={
        409: {"model": ErrorResponse},
        422: {"model": ErrorResponse},
        500: {"model": ErrorResponse},
    },
)
async def prepare_job_for_search(
    payload: JobSearchPreparationRequest,
    session: AsyncSession = Depends(get_db_session),
) -> CandidateSearchFilters:
    """Prepare a vacancy description into rule filters and vector query texts.

    Args:
        payload: Raw vacancy text plus optional external identifiers for reruns.
        session: Active database session.

    Returns:
        CandidateSearchFilters: Search-ready payload that can be passed directly
        to `POST /rag/search`.
    """
    service = JobSearchPreparationService(session)
    try:
        return await service.run(payload)
    except JobSearchPreparationError as exc:
        detail = str(exc)
        status_code = (
            status.HTTP_422_UNPROCESSABLE_ENTITY
            if detail == "Raw text is missing for job preparation"
            else status.HTTP_409_CONFLICT
        )
        raise HTTPException(status_code=status_code, detail=detail) from exc
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        ) from exc


@router.get(
    "/jobs/{job_id}",
    response_model=CandidateSearchFilters,
    responses={404: {"model": ErrorResponse}},
)
async def get_prepared_job_for_search(
    job_id: str,
    session: AsyncSession = Depends(get_db_session),
) -> CandidateSearchFilters:
    """Return the persisted search-ready representation for one vacancy.

    Args:
        job_id: External or generated job identifier used during preparation.
        session: Active database session.

    Returns:
        CandidateSearchFilters: Persisted search-ready payload for the requested
        vacancy, directly reusable as `/rag/search` input.
    """
    service = JobSearchPreparationService(session)
    try:
        return await service.get_result(job_id)
    except JobSearchPreparationError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc


@router.post(
    "/file/{file_id}/extract-entities",
    tags=["Upload and Process"],
    response_model=EntityExtractionRunResponse,
    responses={
        404: {"model": ErrorResponse},
        409: {"model": ErrorResponse},
        500: {"model": ErrorResponse},
    },
)
async def extract_file_entities(
    file_id: str,
    session: AsyncSession = Depends(get_db_session),
) -> EntityExtractionRunResponse:
    """Run MVP LangGraph entity extraction for a stored CV document.

    Args:
        file_id: Identifier of the document to extract entities from.
        session: Active database session.

    Returns:
        EntityExtractionRunResponse: Current extraction run state for the document.
    """
    service = CandidateEntityExtractionService(session)
    try:
        return await service.run(file_id)
    except EntityExtractionGraphError as exc:
        status_code = (
            status.HTTP_404_NOT_FOUND
            if str(exc) == "Document not found"
            else status.HTTP_409_CONFLICT
        )
        raise HTTPException(status_code=status_code, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        ) from exc


@router.get(
    "/file/{file_id}/entities",
    response_model=CandidateEntitiesResponse,
    responses={404: {"model": ErrorResponse}},
)
async def get_file_entities(
    file_id: str,
    session: AsyncSession = Depends(get_db_session),
) -> CandidateEntitiesResponse:
    """Return extracted entities and processing metadata for a CV document.

    Args:
        file_id: Identifier of the document whose extracted entities should be returned.
        session: Active database session.

    Returns:
        CandidateEntitiesResponse: Persisted profile, experiences, skills,
        languages, education, certifications, and extraction run metadata.
    """
    service = CandidateEntityExtractionService(session)
    try:
        return await service.get_result(file_id)
    except EntityExtractionGraphError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc


@router.delete("/file/{file_id}")
async def delete_file(
    request: Request,
    file_id: str,
    session: AsyncSession = Depends(get_db_session),
) -> DeleteFileResponse:
    """Delete a stored file from S3 and remove its database record.

    Args:
        request: FastAPI request with initialized application services.
        file_id: Identifier of the file to remove.
        session: Active database session.

    Returns:
        DeleteFileResponse: Identifier of the deleted file.
    """
    documents = CandidateDocumentRepository(session)
    document = await documents.get_plain_by_id(file_id)
    if document is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found",
        )

    if document.storage_key:
        await request.app.state.s3.delete_file(
            key=document.storage_key,
            bucket_name=document.storage_bucket
            or request.app.state.cv_storage.bucket_name,
        )

    await session.delete(document)
    await session.commit()

    logger.info(
        "RAG file deleted: file_id={file_id}",
        file_id=file_id,
    )
    return DeleteFileResponse(file_id=file_id)
