from typing import Annotated
from urllib.parse import quote, unquote

from fastapi import APIRouter, File, Header, Query, Request, Response, UploadFile
from starlette.concurrency import run_in_threadpool

from app.api.deps import CurrentUser, DBSession
from app.core.exceptions import AppError
from app.schemas.common import ApiResponse
from app.schemas.document import (
    DocumentKind,
    DocumentPage,
    DocumentRead,
    DocumentRename,
    DocumentStorageChange,
)
from app.services import documents

router = APIRouter(prefix="/documents", tags=["documents"])


@router.get("", response_model=ApiResponse[DocumentPage])
def list_documents(
    user: CurrentUser,
    db: DBSession,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 10,
    q: Annotated[str | None, Query(max_length=100)] = None,
    kind: DocumentKind | None = None,
):
    return ApiResponse(
        data=documents.list_documents(db, user, page=page, page_size=page_size, q=q, kind=kind)
    )


@router.post("", status_code=201, response_model=ApiResponse[DocumentRead])
def upload(user: CurrentUser, db: DBSession, file: Annotated[UploadFile, File()]):
    raw = file.file.read(documents.MAX_DOCUMENT_BYTES + 1)
    return ApiResponse(data=documents.upload(db, user, file.filename, raw))


@router.post("/encrypted-upload", status_code=201, response_model=ApiResponse[DocumentRead])
async def encrypted_upload(
    request: Request,
    user: CurrentUser,
    db: DBSession,
    filename: Annotated[str, Header(alias="X-FocusNest-Filename", min_length=1, max_length=4096)],
):
    if request.headers.get("content-type") != "application/octet-stream":
        raise AppError(415, 41501, "Expected an octet-stream upload")
    try:
        name = unquote(filename, errors="strict")
    except UnicodeError:
        raise AppError(422, 42206, "Invalid document filename") from None
    raw = bytearray()
    async for chunk in request.stream():
        if len(raw) + len(chunk) > documents.MAX_DOCUMENT_BYTES:
            raise AppError(413, 41301, "Document exceeds size limit")
        raw.extend(chunk)
    result = await run_in_threadpool(
        documents.upload, db, user, name, bytes(raw), "cloud_encrypted"
    )
    return ApiResponse(data=result)


@router.get("/{document_id}", response_model=ApiResponse[DocumentRead])
def get_document(document_id: str, user: CurrentUser, db: DBSession):
    return ApiResponse(data=documents.get_document(db, user, document_id))


@router.get("/{document_id}/download")
def download(document_id: str, user: CurrentUser, db: DBSession):
    document = documents.owned(db, user, document_id)
    filename = documents.read_metadata(document).filename
    return Response(
        content=documents.read_file(document),
        media_type="application/octet-stream",
        headers={
            "Content-Disposition": "attachment; filename=\"document.txt\"; filename*=UTF-8''"
            + quote(filename, safe=""),
            "X-Content-Type-Options": "nosniff",
        },
    )


@router.patch("/{document_id}", response_model=ApiResponse[DocumentRead])
def rename(document_id: str, payload: DocumentRename, user: CurrentUser, db: DBSession):
    return ApiResponse(data=documents.rename(db, user, document_id, payload))


@router.post("/{document_id}/storage", response_model=ApiResponse[DocumentRead])
def change_storage(
    document_id: str, payload: DocumentStorageChange, user: CurrentUser, db: DBSession
):
    return ApiResponse(data=documents.change_storage(db, user, document_id, payload))


@router.delete("/{document_id}", response_model=ApiResponse[None])
def delete_document(
    document_id: str,
    revision: Annotated[str, Query(min_length=36, max_length=36)],
    user: CurrentUser,
    db: DBSession,
):
    documents.delete_document(db, user, document_id, revision)
    return ApiResponse(message="Document deleted")


@router.get("/{document_id}/preview")
def pdf_preview(
    document_id: str, user: CurrentUser, db: DBSession, page: Annotated[int, Query(ge=1)] = 1
):
    from app.services.document_preview import render_pdf_page

    document = documents.owned(db, user, document_id)
    if document.kind != "pdf":
        raise AppError(422, 42207, "Preview pages only supported for PDF")
    return Response(
        render_pdf_page(documents.read_file(document), page),
        media_type="image/png",
        headers={"X-Content-Type-Options": "nosniff"},
    )
