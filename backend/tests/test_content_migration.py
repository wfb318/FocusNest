import json
import sqlite3
from contextlib import closing
from datetime import date, datetime
from uuid import UUID

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from test_auth import bearer, login, registration
from test_auth import context as context
from test_documents import upload
from test_notes import create

from app.core.content_crypto import ContentCrypto
from app.core.content_keyring import KeyringError, load_keyring
from app.db.base import Base
from app.models import Document, EncryptedJournal, Journal, MigrationReceipt, Note, User
from app.schemas.note import NoteCreate
from app.services import content_migration, documents, encrypted_journals, notes
from scripts.manage_content_keys import main as manage_keys
from scripts.migrate_private_content import main

JOURNAL_DATE = date(2025, 12, 29)
CREATED = datetime(2025, 12, 29, 12, 30, 1)
TITLE = "Synthetic migration title"
BODY = "Synthetic migration body with preserved whitespace  \n"
FILE = b"# Synthetic file\r\n\r\nline  \r\n"


def bind_crypto(monkeypatch, path):
    crypto = ContentCrypto(load_keyring(path))
    for service in (notes, documents, encrypted_journals):
        monkeypatch.setattr(service, "get_content_crypto", lambda: crypto)


def create_test_key(tmp_path, monkeypatch, capsys):
    path = tmp_path / "source.keys"
    assert manage_keys(["create", "--file", str(path), "--key-id", "drill-key"]) == 0
    capsys.readouterr()
    bind_crypto(monkeypatch, path)
    return path


def legacy_journal(db, user_id, entry_date=JOURNAL_DATE):
    entry = Journal(
        user_id=user_id,
        entry_date=entry_date,
        title=TITLE,
        content=BODY,
        created_at=CREATED,
        updated_at=CREATED,
    )
    db.add(entry)
    db.flush()
    return {"id": entry.id, "revision": entry.revision}


def save_selection(path, account, **items):
    selection = content_migration.MigrationSelection(
        account_id=UUID(account),
        items=[content_migration.MigrationItem(kind=kind, **item) for kind, item in items.items()],
    )
    path.write_text(selection.model_dump_json(), encoding="utf-8")


def selected_fields(record):
    return {key: record[key] for key in ("id", "revision")}


def test_selected_migration_roundtrip_and_receipts(context, tmp_path, monkeypatch, capsys):
    create_test_key(tmp_path, monkeypatch, capsys)
    client, connection = context
    payload, user = registration(client)
    headers = bearer(login(client, payload))
    factory = sessionmaker(
        bind=connection, join_transaction_mode="create_savepoint", expire_on_commit=False
    )
    note = create(client, headers, title=TITLE, content=BODY)
    other_note = create(client, headers)
    document = upload(client, headers, filename="synthetic.md", content=FILE)
    with factory.begin() as db:
        journal = legacy_journal(db, user["id"])
    selection = tmp_path / "approved.json"
    save_selection(
        selection,
        user["id"],
        note=selected_fields(note),
        document=selected_fields(document),
        journal=journal,
    )
    command = ["apply", "--selection", str(selection)]
    assert main(command, session_factory=factory) == 0
    result = capsys.readouterr()
    assert TITLE not in result.out and BODY.strip() not in result.out and not result.err
    assert [json.loads(line)["status"] for line in result.out.splitlines()] == ["migrated"] * 3

    with factory() as db:
        stored_note = db.get(Note, note["id"])
        assert stored_note.title is stored_note.content is None
        assert notes.read_body(stored_note) == (TITLE, BODY)
        assert db.get(Note, other_note["id"]).storage_mode == "cloud"
        stored_document = db.get(Document, document["id"])
        assert (
            stored_document.title is stored_document.filename is stored_document.raw_content is None
        )
        assert db.scalar(
            select(Document.preview_data.is_(None)).where(Document.id == document["id"])
        )
        assert documents.read_file(stored_document) == FILE
        assert documents.read_metadata(stored_document).filename == "synthetic.md"
        assert db.get(Journal, journal["id"]) is None
        stored_journal = db.get(EncryptedJournal, journal["id"])
        assert stored_journal.created_at == stored_journal.updated_at == CREATED
        restored_journal = encrypted_journals.read(stored_journal)
        assert (restored_journal.entry_date, restored_journal.title, restored_journal.content) == (
            JOURNAL_DATE,
            TITLE,
            BODY,
        )
        assert (
            len(
                db.scalars(
                    select(MigrationReceipt).where(MigrationReceipt.user_id == user["id"])
                ).all()
            )
            == 3
        )

    assert main(command, session_factory=factory) == 0
    assert [json.loads(line)["status"] for line in capsys.readouterr().out.splitlines()] == [
        "already_applied"
    ] * 3

    catalog = tmp_path / "catalog.json"
    # Full catalog comparison is exercised on an isolated restored database below.
    assert main(["export-catalog", "--output", str(catalog)], session_factory=factory) == 0
    assert TITLE not in catalog.read_text(encoding="utf-8")


def test_migration_interruption_rollback_and_selection_ownership(
    context, tmp_path, monkeypatch, capsys
):
    create_test_key(tmp_path, monkeypatch, capsys)
    client, connection = context
    payload, user = registration(client)
    _, unrelated = registration(client)
    headers = bearer(login(client, payload))
    factory = sessionmaker(bind=connection, join_transaction_mode="create_savepoint")
    note = create(client, headers, title=TITLE, content=BODY)
    document = upload(client, headers)
    selection = tmp_path / "selected.json"
    assert (
        main(
            ["list", "--account", user["id"], "--kind", "note"],
            session_factory=factory,
        )
        == 0
    )
    [candidate] = json.loads(capsys.readouterr().out)
    assert candidate["id"] == note["id"] and candidate["mode"] == "cloud"
    assert set(candidate) == {"id", "revision", "mode", "updated_at"}
    plan_args = ["--kind", "note", "--id", note["id"], "--output", str(selection)]
    assert main(["plan", "--account", unrelated["id"], *plan_args], session_factory=factory) == 1
    assert not selection.exists()
    assert main(["plan", "--account", user["id"], *plan_args], session_factory=factory) == 0
    assert json.loads(selection.read_bytes())["items"][0]["revision"] == note["revision"]
    assert main(["plan", "--account", user["id"], *plan_args], session_factory=factory) == 1
    capsys.readouterr()

    batch = tmp_path / "batch.json"
    save_selection(
        batch, user["id"], note=selected_fields(note), document=selected_fields(document)
    )
    original = documents.flush_and_verify

    def interrupt_after_flush(*args):
        original(*args)
        raise KeyboardInterrupt

    monkeypatch.setattr(documents, "flush_and_verify", interrupt_after_flush)
    command = ["apply", "--selection", str(batch)]
    assert main(command, session_factory=factory) == 130
    result = capsys.readouterr()
    assert json.loads(result.out)["status"] == "migrated"
    assert json.loads(result.err)["status"] == "interrupted"

    def fail_after_flush(*args):
        original(*args)
        raise KeyringError()

    monkeypatch.setattr(documents, "flush_and_verify", fail_after_flush)
    assert main(command, session_factory=factory) == 1
    assert [json.loads(line)["status"] for line in capsys.readouterr().out.splitlines()] == [
        "already_applied",
        "failed",
    ]
    with factory() as db:
        assert db.get(Note, note["id"]).storage_mode == "cloud_encrypted"
        assert db.get(Document, document["id"]).storage_mode == "cloud"
        assert (
            db.get(MigrationReceipt, (user["id"], "document", document["id"], document["revision"]))
            is None
        )
    monkeypatch.setattr(documents, "flush_and_verify", original)
    assert main(command, session_factory=factory) == 0
    assert [json.loads(line)["status"] for line in capsys.readouterr().out.splitlines()] == [
        "already_applied",
        "migrated",
    ]


def test_separate_backups_restore_and_block_stale_plaintext(tmp_path, monkeypatch, capsys):
    source_key = create_test_key(tmp_path, monkeypatch, capsys)
    source_file = tmp_path / "original.sqlite"
    source = create_engine(f"sqlite:///{source_file.as_posix()}")
    Base.metadata.create_all(source)
    factory = sessionmaker(bind=source, expire_on_commit=False)
    with factory.begin() as db:
        user = User(username="synthetic", email="synthetic@example.com", password_hash="synthetic")
        db.add(user)
        db.flush()
        legacy = legacy_journal(db, user.id)
        entry = legacy_journal(db, user.id, date(2025, 12, 30))
        user_id = user.id
    with factory() as db:
        user = db.get(User, user_id)
        note = notes.create(
            db, user, NoteCreate(title=TITLE, content=BODY, storage_mode="cloud_encrypted")
        )
        document = documents.upload(db, user, "backup.md", FILE, storage_mode="cloud_encrypted")

    def database_backup(target):
        with (
            closing(sqlite3.connect(source_file)) as reader,
            closing(sqlite3.connect(target)) as writer,
        ):
            reader.backup(writer)

    stale_file = tmp_path / "older-backup.sqlite"
    database_backup(stale_file)
    selection = tmp_path / "journal-selection.json"
    save_selection(selection, user_id, journal=entry)
    assert main(["apply", "--selection", str(selection)], session_factory=factory) == 0
    # Model a separate journal whose online copy was removed after a local import.
    with factory.begin() as db:
        db.delete(db.get(Journal, legacy["id"]))
    catalog = tmp_path / "trusted-catalog.json"
    assert main(["export-catalog", "--output", str(catalog)], session_factory=factory) == 0
    approved_file = tmp_path / "database-backup.sqlite"
    database_backup(approved_file)
    key_backup_dir = tmp_path / "key-backup"
    key_backup_dir.mkdir()
    restored_key = key_backup_dir / "restored.keys"
    assert manage_keys(["backup", "--file", str(source_key), "--output", str(restored_key)]) == 0
    source.dispose()
    capsys.readouterr()

    command = ["verify-restore", "--catalog", str(catalog)]
    stale = create_engine(f"sqlite:///{stale_file.as_posix()}")
    assert main(command, session_factory=sessionmaker(bind=stale)) == 1
    assert json.loads(capsys.readouterr().out) == {
        "status": "catalog_mismatch",
        "unexpected": 2,
        "missing": 1,
    }
    stale.dispose()

    restored = create_engine(f"sqlite:///{approved_file.as_posix()}")
    restored_factory = sessionmaker(bind=restored)

    def missing_key():
        raise KeyringError()

    monkeypatch.setattr(notes, "get_content_crypto", missing_key)
    assert main(command, session_factory=restored_factory) == 1
    assert json.loads(capsys.readouterr().out)["status"] == "failed"
    bind_crypto(monkeypatch, restored_key)
    assert main(command, session_factory=restored_factory) == 0
    assert json.loads(capsys.readouterr().out) == {
        "status": "verified",
        "records": 3,
        "encrypted_checked": 3,
    }
    with restored_factory() as db:
        assert db.get(Journal, legacy["id"]) is None
        assert encrypted_journals.read(db.get(EncryptedJournal, entry["id"])).content == BODY
        assert notes.read_body(db.get(Note, note.id)) == (TITLE, BODY)
        assert documents.read_file(db.get(Document, document.id)) == FILE
    with restored_factory.begin() as db:
        db.get(Document, document.id).encrypted_file = "corrupt"
    assert main(command, session_factory=restored_factory) == 1
    assert json.loads(capsys.readouterr().out)["id"] == document.id
    restored.dispose()
