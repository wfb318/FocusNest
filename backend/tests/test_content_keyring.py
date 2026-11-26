import base64
import json
import os
from pathlib import Path
from uuid import uuid4

import pytest
from pydantic import SecretStr

from app.core import content_keyring as keyring_module
from app.core.config import Settings, get_settings
from app.core.content_crypto import ContentContext, ContentCrypto, get_content_crypto
from app.core.content_keyring import (
    ContentKeyring,
    KeyringError,
    check_file_permissions,
    load_keyring,
    write_new_keyring,
)
from scripts.manage_content_keys import main


def ring():
    return ContentKeyring("key-one", {"key-one": os.urandom(32)})


def test_key_material_is_not_in_repr_settings_or_tool_output(tmp_path, capsys):
    keyring = ring()
    encoded = base64.b64encode(keyring.key("key-one")).decode()
    assert encoded not in repr(keyring) and repr(keyring.key("key-one")) not in repr(keyring)
    assert "_keys" not in repr(keyring)
    assert "hidden.json" not in repr(
        Settings(_env_file=None, content_keyring_file=tmp_path / "hidden.json")
    )
    assert Settings(_env_file=None, content_keyring_file="").content_keyring_file is None
    assert main(["create", "--file", str(tmp_path / "created.json"), "--key-id", "key-new"]) == 0
    output = capsys.readouterr()
    written = json.loads((tmp_path / "created.json").read_text())
    assert written["keys"]["key-new"] not in output.out + output.err
    assert str(tmp_path) not in output.out + output.err


def test_restricted_file_roundtrip_backup_and_restore(tmp_path):
    keyring = ring()
    source = tmp_path / "primary.json"
    backup = tmp_path / "backup.json"
    write_new_keyring(source, keyring)
    check_file_permissions(source, source.stat())
    assert main(["backup", "--file", str(source), "--output", str(backup)]) == 0
    context = ContentContext(str(uuid4()), "note", str(uuid4()), "payload", str(uuid4()))
    encrypted = ContentCrypto(load_keyring(source)).encrypt(b"backup recovery sample", context)
    source.unlink()  # isolated temporary keyring, not a user/platform key
    assert (
        ContentCrypto(load_keyring(backup)).decrypt(encrypted, context) == b"backup recovery sample"
    )


def test_cli_rotation_preserves_old_file_and_all_existing_keys(tmp_path, capsys):
    source = tmp_path / "primary.json"
    next_file = tmp_path / "next.json"
    write_new_keyring(source, ring())
    original = source.read_bytes()
    assert (
        main(["rotate", "--file", str(source), "--output", str(next_file), "--key-id", "key-two"])
        == 0
    )
    assert source.read_bytes() == original
    updated = load_keyring(next_file)
    assert updated.active_key_id == "key-two"
    assert updated.key("key-one") == ContentKeyring.from_json(original).key("key-one")
    assert main(["check", "--file", str(next_file)]) == 0
    assert (
        main(["rotate", "--file", str(source), "--output", str(source), "--key-id", "key-three"])
        == 1
    )
    assert source.read_bytes() == original
    output = capsys.readouterr()
    for value in json.loads(next_file.read_bytes())["keys"].values():
        assert value not in output.out + output.err


@pytest.mark.parametrize(
    "mutation",
    [
        {"version": True},
        {"version": 2},
        {"active_key_id": "missing"},
        {"extra": "key data"},
        {"keys": {"one": "not-base64"}},
        {"keys": {"one": base64.b64encode(b"short").decode()}},
        {"keys": {"../one": base64.b64encode(os.urandom(32)).decode()}},
    ],
)
def test_malformed_keyring_fails_without_exposing_values(mutation):
    value = {**json.loads(ring().to_json()), **mutation}
    with pytest.raises(KeyringError) as failure:
        ContentKeyring.from_json(json.dumps(value).encode())
    assert "not-base64" not in failure.value.message and "key data" not in failure.value.message


def test_duplicate_json_duplicate_material_excess_keys_and_non_json_are_rejected():
    for raw in (b"not json", b'{"version":1,"version":1}', b"[]", b"x" * 65537, b"[" * 2000):
        with pytest.raises(KeyringError):
            ContentKeyring.from_json(raw)
    same = os.urandom(32)
    with pytest.raises(KeyringError):
        ContentKeyring("one", {"one": same, "two": same})
    with pytest.raises(KeyringError):
        ContentKeyring("k0", {f"k{i}": os.urandom(32) for i in range(33)})


def test_missing_relative_project_or_directory_paths_cannot_be_used(tmp_path):
    for path in (
        None,
        Path("relative-keyring.json"),
        Path(__file__).resolve().parents[1] / "secret.json",
        tmp_path / "absent.json",
        tmp_path,
    ):
        with pytest.raises(KeyringError):
            load_keyring(path)


def test_missing_configuration_fails_closed_and_does_not_generate_or_reuse_jwt(
    monkeypatch, tmp_path
):
    settings = get_settings()
    get_content_crypto.cache_clear()
    monkeypatch.setattr(settings, "content_keyring_file", None)
    try:
        with pytest.raises(KeyringError):
            get_content_crypto()
        assert list(tmp_path.iterdir()) == []
        secret = "test-only-signing-key-never-to-reuse"
        for encoding in ("raw", "base64", "base64url", "hex"):
            raw = secret[:32].encode() if encoding == "raw" else os.urandom(32)
            signing_secret = {
                "raw": secret[:32],
                "base64": base64.b64encode(raw).decode(),
                "base64url": base64.urlsafe_b64encode(raw).decode().rstrip("="),
                "hex": raw.hex(),
            }[encoding]
            path = tmp_path / f"{uuid4()}.json"
            write_new_keyring(path, ContentKeyring("invalid-reuse", {"invalid-reuse": raw}))
            monkeypatch.setattr(settings, "jwt_secret", SecretStr(signing_secret))
            monkeypatch.setattr(settings, "content_keyring_file", path)
            with pytest.raises(KeyringError):
                get_content_crypto()
    finally:
        get_content_crypto.cache_clear()


def test_configured_factory_loads_a_separate_keyring_and_requires_explicit_reload(
    monkeypatch, tmp_path
):
    path = tmp_path / "configured.json"
    write_new_keyring(path, ring())
    settings = get_settings()
    monkeypatch.setattr(settings, "content_keyring_file", path)
    monkeypatch.setattr(
        settings, "jwt_secret", SecretStr("test-signing-secret-independent-of-content")
    )
    get_content_crypto.cache_clear()
    try:
        first = get_content_crypto()
        assert first is get_content_crypto()
        path.unlink()
        get_content_crypto.cache_clear()
        with pytest.raises(KeyringError):
            get_content_crypto()
    finally:
        get_content_crypto.cache_clear()


def test_overwrite_and_invalid_cli_arguments_leave_existing_file_unchanged(tmp_path, capsys):
    path = tmp_path / "existing.json"
    write_new_keyring(path, ring())
    before = path.read_bytes()
    with pytest.raises(KeyringError):
        write_new_keyring(path, ring())
    for args in (
        ["create", "--file", str(path), "--key-id", "new"],
        ["rotate", "--file", str(path), "--key-id", "new"],
        ["backup", "--file", str(path), "--output", str(tmp_path / "out.json"), "--key-id", "bad"],
    ):
        assert main(args) == 1
    assert path.read_bytes() == before
    assert base64.b64encode(load_keyring(path).key("key-one")).decode() not in str(
        capsys.readouterr()
    )


def test_broad_file_permissions_are_rejected(tmp_path):
    path = tmp_path / "inherited.json"
    path.write_bytes(
        ring().to_json()
    )  # default inherited ACL/mode, deliberately not a secure writer
    if os.name != "nt":
        path.chmod(0o644)
    with pytest.raises(KeyringError):
        load_keyring(path)


def test_file_replacement_after_permission_check_is_rejected(tmp_path, monkeypatch):
    source = tmp_path / "original.json"
    replacement = tmp_path / "replacement.json"
    write_new_keyring(source, ring())
    write_new_keyring(replacement, ring())
    original_check = keyring_module.check_file_permissions

    def switch_file(path, info):
        original_check(path, info)
        os.replace(replacement, source)

    monkeypatch.setattr(keyring_module, "check_file_permissions", switch_file)
    with pytest.raises(KeyringError):
        load_keyring(source)


def test_existing_api_error_handler_does_not_expose_key_paths_or_private_input(
    tmp_path, monkeypatch, caplog
):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from app.core.exceptions import register_exception_handlers

    missing = tmp_path / "private-key-location.json"
    settings = get_settings()
    monkeypatch.setattr(settings, "content_keyring_file", missing)
    get_content_crypto.cache_clear()
    app = FastAPI()
    register_exception_handlers(app)
    keyring = ring()
    crypto = ContentCrypto(keyring)
    context = ContentContext(str(uuid4()), "note", str(uuid4()), "payload", str(uuid4()))

    @app.get("/probe/missing")
    def unavailable():
        return get_content_crypto()

    @app.get("/probe/corrupt")
    def corrupt():
        return crypto.decrypt("private plaintext must never be returned", context)

    try:
        with TestClient(app) as client:
            unavailable_response = client.get("/probe/missing")
            corrupt_response = client.get("/probe/corrupt")
        assert unavailable_response.status_code == 503
        assert corrupt_response.status_code == 422
        output = unavailable_response.text + corrupt_response.text + caplog.text
        assert str(missing) not in output and "private plaintext" not in output
        assert base64.b64encode(keyring.key("key-one")).decode() not in output
    finally:
        get_content_crypto.cache_clear()
