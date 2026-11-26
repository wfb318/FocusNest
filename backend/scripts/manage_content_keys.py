"""Offline key administration. Writes restricted new files, never overwrites or prints keys."""

import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.content_crypto import ContentContext, ContentCrypto  # noqa: E402
from app.core.content_keyring import (  # noqa: E402
    KEY_ID,
    ContentKeyring,
    KeyringError,
    load_keyring,
    write_new_keyring,
)
from app.core.exceptions import AppError  # noqa: E402


def verify(keyring: ContentKeyring) -> None:
    context = ContentContext(
        owner_id="00000000-0000-4000-8000-000000000001",
        object_type="key_test",
        object_id="00000000-0000-4000-8000-000000000002",
        field_name="probe",
        revision="00000000-0000-4000-8000-000000000003",
    )
    for key_id in keyring._keys:
        selected = ContentKeyring(key_id, keyring._keys)
        crypto = ContentCrypto(selected)
        plaintext = b"FocusNest isolated keyring recovery probe"
        if crypto.decrypt(crypto.encrypt(plaintext, context), context) != plaintext:
            raise KeyringError()


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("create", "check", "rotate", "backup"))
    parser.add_argument("--file", type=Path, required=True, help="Absolute external keyring path")
    parser.add_argument("--output", type=Path, help="New external file for rotate/backup")
    parser.add_argument("--key-id", help="Public key identifier for create/rotate")
    args = parser.parse_args(argv)
    try:
        if args.action in ("create", "rotate"):
            if not args.key_id or not KEY_ID.fullmatch(args.key_id):
                raise KeyringError()
        elif args.key_id:
            raise KeyringError()
        if (args.action in ("rotate", "backup")) != (args.output is not None):
            raise KeyringError()
        if args.action == "create":
            keyring = ContentKeyring(args.key_id, {args.key_id: os.urandom(32)})
            write_new_keyring(args.file, keyring)
        else:
            keyring = load_keyring(args.file)
            verify(keyring)
            if args.action == "rotate":
                keyring = keyring.with_new_active_key(args.key_id)
                write_new_keyring(args.output, keyring)
            elif args.action == "backup":
                write_new_keyring(args.output, keyring)
        verify(keyring)
        print("Content keyring operation verified. Key material was not displayed.")
        return 0
    except AppError:
        print(
            "Keyring operation failed. Check configuration, external paths and permissions. "
            "Existing files were not overwritten; any new output must be verified before use.",
            file=sys.stderr,
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
