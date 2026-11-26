"""Operator commands for selected content migration and isolated restore verification."""

import argparse
import json
import sys
from pathlib import Path
from uuid import UUID

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pydantic import ValidationError  # noqa: E402
from sqlalchemy.exc import SQLAlchemyError  # noqa: E402

from app.core.exceptions import AppError  # noqa: E402
from app.db.session import SessionLocal  # noqa: E402
from app.services import content_migration as migration  # noqa: E402


def report(data: dict | list, *, output=None) -> None:
    print(json.dumps(data, ensure_ascii=True, default=str), file=output or sys.stdout, flush=True)


def save_new(path: Path, model) -> None:
    with path.open("x", encoding="utf-8") as file:
        file.write(model.model_dump_json(indent=2) + "\n")


def apply_selection(selection: migration.MigrationSelection, session_factory) -> int:
    failed = False
    for item in selection.items:
        identity = {
            **item.model_dump(mode="json"),
            "account_id": str(selection.account_id),
        }
        try:
            with session_factory() as db, db.begin():
                result = migration.migrate_item(db, selection.account_id, item)
        except (AppError, ValidationError, SQLAlchemyError, UnicodeError) as error:
            failed = True
            code = error.code if isinstance(error, AppError) else "verification_or_database_error"
            report({**identity, "status": "failed", "code": code})
        else:
            report({**identity, **result})
    return int(failed)


def check_restore(expected: migration.RestoreCatalog, session_factory) -> int:
    with session_factory() as db, db.begin():
        restored = set(migration.restore_catalog(db).items)
        approved = set(expected.items)
        if restored != approved:
            report(
                {
                    "status": "catalog_mismatch",
                    "unexpected": len(restored - approved),
                    "missing": len(approved - restored),
                }
            )
            return 1
        checked = 0
        for item in expected.items:
            if item.mode == "cloud_encrypted":
                try:
                    migration.verify_restored_item(db, item)
                except (AppError, ValidationError, SQLAlchemyError, UnicodeError) as error:
                    code = error.code if isinstance(error, AppError) else "restore_check_failed"
                    report({**item.model_dump(mode="json"), "status": "failed", "code": code})
                    return 1
                checked += 1
    report({"status": "verified", "records": len(expected.items), "encrypted_checked": checked})
    return 0


def main(argv=None, *, session_factory=SessionLocal) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    inventory = commands.add_parser("list", help="List one account's source metadata")
    plan = commands.add_parser("plan", help="Freeze explicitly selected IDs and revisions")
    for command in (inventory, plan):
        command.add_argument("--account", type=UUID, required=True)
        command.add_argument("--kind", choices=migration.SOURCE_MODELS, required=True)
    inventory.add_argument("--after", type=UUID)
    plan.add_argument("--id", type=UUID, required=True, action="append")
    plan.add_argument("--output", type=Path, required=True)
    apply = commands.add_parser("apply", help="Migrate only the records in an approved selection")
    apply.add_argument("--selection", type=Path, required=True)
    catalog = commands.add_parser(
        "export-catalog", help="Save current content identities for recovery"
    )
    catalog.add_argument("--output", type=Path, required=True)
    restore = commands.add_parser("verify-restore", help="Check an isolated restored database")
    restore.add_argument("--catalog", type=Path, required=True)
    args = parser.parse_args(argv)

    try:
        if args.command == "apply":
            with args.selection.open("rb") as file:
                data = file.read(1_048_577)
            if len(data) > 1_048_576:
                raise ValueError("Selection file too large")
            selection = migration.MigrationSelection.model_validate_json(data)
            return apply_selection(selection, session_factory)
        if args.command == "verify-restore":
            return check_restore(
                migration.RestoreCatalog.model_validate_json(args.catalog.read_bytes()),
                session_factory,
            )
        with session_factory() as db:
            if args.command == "list":
                report(
                    migration.source_summary(
                        db, str(args.account), args.kind, str(args.after) if args.after else None
                    )
                )
            elif args.command == "plan":
                if len(args.id) > migration.MAX_BATCH or len(set(args.id)) != len(args.id):
                    raise ValueError("Invalid selection size or duplicate ID")
                save_new(
                    args.output, migration.make_selection(db, args.account, args.kind, args.id)
                )
            else:
                save_new(args.output, migration.restore_catalog(db))
        return 0
    except KeyboardInterrupt:
        report({"status": "interrupted"}, output=sys.stderr)
        return 130
    except (AppError, ValueError, OSError, SQLAlchemyError) as error:
        code = error.code if isinstance(error, AppError) else "invalid_input_or_unavailable"
        report({"status": "failed", "code": code}, output=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
