import re
from uuid import uuid4

from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.core.content_crypto import ContentContext, get_content_crypto, invalid_ciphertext
from app.core.exceptions import AppError
from app.models.document import Document
from app.models.user import User, utcnow
from app.repositories import documents as repository
from app.schemas.document import (
    DocumentMetadata,
    DocumentPage,
    DocumentRead,
    DocumentRename,
    DocumentStorageChange,
    DocumentStorageMode,
    DocumentSummary,
)
from app.services.document_preview import MAX_OFFICE_BYTES, extract_preview

MAX_DOCUMENT_BYTES = MAX_OFFICE_BYTES
TEXT_LIMIT = 512 * 1024
FORMATS = {
    "md": "markdown",
    "markdown": "markdown",
    "txt": "text",
    "pdf": "pdf",
    "docx": "word",
    "pptx": "presentation",
    "xlsx": "spreadsheet",
    "xls": "spreadsheet",
}


def validate_file(filename: str | None, raw: bytes) -> tuple[str, str, str]:
    # Names are metadata only, never filesystem paths.
    name = re.split(r"[/\\]", filename or "")[-1].strip()
    if not name or len(name) > 255 or any(ord(c) < 32 or ord(c) == 127 for c in name):
        raise AppError(422, 42206, "Invalid document filename")
    extension = name.rsplit(".", 1)[-1].lower() if "." in name else ""
    if extension not in FORMATS:
        raise AppError(415, 41501, "Unsupported document format")
    limit = TEXT_LIMIT if extension in ("md", "markdown", "txt") else MAX_DOCUMENT_BYTES
    if len(raw) > limit:
        raise AppError(413, 41301, "Document exceeds size limit")
    if extension not in ("md", "markdown", "txt"):
        return name, FORMATS[extension], ""
    try:
        content = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise AppError(422, 42206, "Document must be UTF-8 text") from None
    if not content.strip() or re.search(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", content):
        raise AppError(422, 42206, "Document must be nonblank plain text")
    if len(content) > 100000:
        raise AppError(422, 42206, "Document exceeds 100000 characters")
    return name, "text" if extension == "txt" else "markdown", content


def owned(db: Session, user: User, document_id: str, *, lock=False) -> Document:
    document = repository.find_owned(db, user.id, document_id, lock=lock)
    if document is None:
        raise AppError(404, 40406, "Document not found")
    return document


def metadata_context(document: Document) -> ContentContext:
    return ContentContext(document.user_id, "document", document.id, "metadata", document.revision)


def file_context(document: Document) -> ContentContext:
    # File bytes are immutable for this document ID. Renaming changes only metadata.
    return ContentContext(document.user_id, "document", document.id, "file", document.id)


def read_metadata(document: Document) -> DocumentMetadata:
    if document.storage_mode == "cloud_encrypted":
        if not document.encrypted_metadata:
            raise invalid_ciphertext()
        plaintext = get_content_crypto().decrypt(
            document.encrypted_metadata, metadata_context(document)
        )
        try:
            return DocumentMetadata.model_validate_json(plaintext)
        except ValidationError:
            raise invalid_ciphertext() from None
    return DocumentMetadata(
        title=document.title, filename=document.filename, preview=document.preview_data
    )


def read_file(document: Document) -> bytes:
    if document.storage_mode == "cloud_encrypted":
        if not document.encrypted_file:
            raise invalid_ciphertext()
        raw = get_content_crypto().decrypt(document.encrypted_file, file_context(document))
    else:
        raw = document.raw_content
    if raw is None or len(raw) != document.size_bytes:
        raise invalid_ciphertext()
    return raw


def read(document: Document, metadata: DocumentMetadata, raw: bytes | None = None) -> DocumentRead:
    fields = {
        name: getattr(document, name)
        for name in DocumentSummary.model_fields
        if name not in ("title", "filename")
    }
    content = ""
    if document.kind in ("markdown", "text"):
        content = (read_file(document) if raw is None else raw).decode("utf-8-sig")
    return DocumentRead(
        **fields,
        title=metadata.title,
        filename=metadata.filename,
        preview=metadata.preview,
        content=content,
    )


def write_metadata(document: Document, metadata: DocumentMetadata) -> None:
    if document.storage_mode == "cloud_encrypted":
        document.encrypted_metadata = get_content_crypto().encrypt(
            metadata.model_dump_json().encode("utf-8"), metadata_context(document)
        )
        document.title = None
        document.filename = None
        document.preview_data = None
    else:
        document.title = metadata.title
        document.filename = metadata.filename
        document.preview_data = (
            metadata.preview.model_dump(mode="json") if metadata.preview else None
        )
        document.encrypted_metadata = None


def write_file(document: Document, raw: bytes) -> None:
    if document.storage_mode == "cloud_encrypted":
        document.encrypted_file = get_content_crypto().encrypt(raw, file_context(document))
        document.raw_content = None
    else:
        document.raw_content = raw
        document.encrypted_file = None


def flush_and_verify(
    db: Session,
    document: Document,
    metadata: DocumentMetadata,
    raw: bytes | None = None,
) -> DocumentRead:
    mode = document.storage_mode
    db.flush()
    db.refresh(document)
    verified_metadata = read_metadata(document)
    verified_raw = read_file(document) if raw is not None else None
    if document.storage_mode != mode or verified_metadata != metadata or verified_raw != raw:
        raise invalid_ciphertext()
    return read(document, verified_metadata, verified_raw)


def persist(
    db: Session, document: Document, metadata: DocumentMetadata, raw: bytes | None = None
) -> DocumentRead:
    result = flush_and_verify(db, document, metadata, raw)
    db.commit()
    return result


def upload(
    db: Session,
    user: User,
    filename: str | None,
    raw: bytes,
    storage_mode: DocumentStorageMode = "cloud",
) -> DocumentRead:
    name, kind, _ = validate_file(filename, raw)
    preview = (
        extract_preview(name.rsplit(".", 1)[-1].lower(), raw)
        if kind not in ("markdown", "text")
        else None
    )
    title = name.rsplit(".", 1)[0].strip()[:200] or "导入的文档"
    document = Document(
        id=str(uuid4()),
        user_id=user.id,
        kind=kind,
        size_bytes=len(raw),
        storage_mode=storage_mode,
        revision=str(uuid4()),
    )
    metadata = DocumentMetadata(title=title, filename=name, preview=preview)
    write_file(document, raw)
    write_metadata(document, metadata)
    db.add(document)
    return persist(db, document, metadata, raw)


def get_document(db: Session, user: User, document_id: str) -> DocumentRead:
    document = owned(db, user, document_id)
    return read(document, read_metadata(document))


def list_documents(db: Session, user: User, **filters) -> DocumentPage:
    items, total = repository.list_owned(db, user.id, **filters)
    return DocumentPage(
        items=[DocumentSummary.model_validate(item) for item in items],
        total=total,
        page=filters["page"],
        page_size=filters["page_size"],
    )


def check_revision(document: Document, revision: str):
    if document.revision != revision:
        raise AppError(409, 40908, "Document changed; reload first")


def rename(db: Session, user: User, document_id: str, payload: DocumentRename) -> DocumentRead:
    document = owned(db, user, document_id, lock=True)
    check_revision(document, payload.expected_revision)
    metadata = read_metadata(document)
    metadata.title = payload.title
    document.revision = str(uuid4())
    document.updated_at = utcnow()
    write_metadata(document, metadata)
    return persist(db, document, metadata)


def stage_storage_change(
    db: Session, user: User, document_id: str, payload: DocumentStorageChange
) -> DocumentRead:
    document = owned(db, user, document_id, lock=True)
    check_revision(document, payload.expected_revision)
    metadata = read_metadata(document)
    if document.storage_mode == payload.storage_mode:
        return read(document, metadata)
    raw = read_file(document)
    document.storage_mode = payload.storage_mode
    document.revision = str(uuid4())
    document.updated_at = utcnow()
    write_file(document, raw)
    write_metadata(document, metadata)
    return flush_and_verify(db, document, metadata, raw)


def change_storage(
    db: Session, user: User, document_id: str, payload: DocumentStorageChange
) -> DocumentRead:
    result = stage_storage_change(db, user, document_id, payload)
    db.commit()
    return result


def delete_document(db: Session, user: User, document_id: str, revision: str):
    document = owned(db, user, document_id, lock=True)
    check_revision(document, revision)
    db.delete(document)
    db.commit()
