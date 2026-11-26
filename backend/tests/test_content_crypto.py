import base64
import json
from dataclasses import replace
from uuid import uuid4

import pytest
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.keywrap import aes_key_unwrap

from app.core.content_crypto import (
    MAX_ENVELOPE_BYTES,
    MAX_PLAINTEXT_BYTES,
    ContentContext,
    ContentCrypto,
)
from app.core.content_keyring import ContentKeyring
from app.core.exceptions import AppError


@pytest.fixture
def context():
    return ContentContext(str(uuid4()), "note", str(uuid4()), "payload", str(uuid4()))


@pytest.fixture
def keyring():
    return ContentKeyring("key-old", {"key-old": AESGCM.generate_key(bit_length=256)})


@pytest.mark.parametrize("plaintext", [b"", "私密标题\n正文🙂".encode(), bytes(range(256))])
def test_roundtrip_text_binary_and_empty_payload_without_plaintext_in_envelope(
    context, keyring, plaintext
):
    crypto = ContentCrypto(keyring)
    envelope = crypto.encrypt(plaintext, context)
    assert crypto.decrypt(envelope, context) == plaintext
    data = json.loads(envelope)
    assert data["version"] == 1 and data["algorithm"] == "A256GCM"
    assert len(base64.b64decode(data["nonce"])) == 12
    assert len(base64.b64decode(data["wrapped_key"])) == 40
    assert len(base64.b64decode(data["ciphertext"])) == len(plaintext) + 16
    assert context.owner_id not in envelope
    assert "私密" not in envelope and "正文" not in envelope


def test_each_write_has_a_fresh_data_key_and_nonce_and_documented_aad(context, keyring):
    crypto = ContentCrypto(keyring)
    envelopes = [json.loads(crypto.encrypt(b"same content", context)) for _ in range(100)]
    assert len({item["nonce"] for item in envelopes}) == 100
    assert len({item["wrapped_key"] for item in envelopes}) == 100
    sample = envelopes[0]
    data_key = aes_key_unwrap(keyring.key("key-old"), base64.b64decode(sample["wrapped_key"]))
    # Independent use of cryptography confirms the wire contract, not just our inverse function.
    aad = json.dumps(
        {
            "domain": "focusnest/content",
            "envelope": {k: v for k, v in sample.items() if k != "ciphertext"},
            "context": {
                "owner_id": context.owner_id,
                "object_type": "note",
                "object_id": context.object_id,
                "field_name": "payload",
                "revision": context.revision,
            },
        },
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    ).encode("ascii")
    assert (
        AESGCM(data_key).decrypt(
            base64.b64decode(sample["nonce"]), base64.b64decode(sample["ciphertext"]), aad
        )
        == b"same content"
    )


@pytest.mark.parametrize("field", ["ciphertext", "nonce", "wrapped_key"])
def test_authenticated_bytes_reject_tampering_without_returning_plaintext(context, keyring, field):
    crypto = ContentCrypto(keyring)
    envelope = json.loads(crypto.encrypt(b"private body", context))
    changed = bytearray(base64.b64decode(envelope[field]))
    changed[0] ^= 1
    envelope[field] = base64.b64encode(changed).decode()
    with pytest.raises(AppError) as failure:
        crypto.decrypt(json.dumps(envelope), context)
    assert failure.value.code == 42230
    assert "private body" not in failure.value.message


@pytest.mark.parametrize(
    "field,value",
    [
        ("owner_id", str(uuid4())),
        ("object_id", str(uuid4())),
        ("object_type", "journal"),
        ("field_name", "preview"),
        ("revision", str(uuid4())),
    ],
)
def test_ciphertext_cannot_be_moved_to_another_owner_object_field_or_revision(
    context, keyring, field, value
):
    crypto = ContentCrypto(keyring)
    with pytest.raises(AppError):
        crypto.decrypt(crypto.encrypt(b"private body", context), replace(context, **{field: value}))


def test_wrong_key_and_unknown_key_never_fall_back_to_another_key(context, keyring):
    envelope = ContentCrypto(keyring).encrypt(b"private body", context)
    wrong = ContentKeyring("key-old", {"key-old": AESGCM.generate_key(bit_length=256)})
    missing = ContentKeyring("key-new", {"key-new": AESGCM.generate_key(bit_length=256)})
    with pytest.raises(AppError) as invalid:
        ContentCrypto(wrong).decrypt(envelope, context)
    assert invalid.value.code == 42230
    with pytest.raises(AppError) as unavailable:
        ContentCrypto(missing).decrypt(envelope, context)
    assert unavailable.value.code == 50330


@pytest.mark.parametrize(
    "mutation",
    [
        {"version": 2},
        {"version": True},
        {"algorithm": "NONE"},
        {"key_wrap": "RAW"},
        {"key_id": "../key"},
        {"nonce": ""},
        {"wrapped_key": "x"},
        {"ciphertext": "AAAA"},
        {"ciphertext": None},
        {"title": "Never accept a plaintext shadow"},
    ],
)
def test_malformed_or_downgraded_envelopes_are_rejected(context, keyring, mutation):
    crypto = ContentCrypto(keyring)
    data = {**json.loads(crypto.encrypt(b"protected", context)), **mutation}
    with pytest.raises(AppError) as failure:
        crypto.decrypt(json.dumps(data), context)
    assert failure.value.code == 42230


@pytest.mark.parametrize(
    "envelope",
    [
        "plain text",
        "null",
        "[]",
        '{"version":1,"version":1}',
        "[" * 2000,
        "x" * (MAX_ENVELOPE_BYTES + 1),
    ],
    ids=["plain", "null", "array", "duplicate", "deep", "oversized"],
)
def test_plaintext_duplicate_json_and_oversized_input_never_decrypt(context, keyring, envelope):
    with pytest.raises(AppError):
        ContentCrypto(keyring).decrypt(envelope, context)


def test_rotation_and_backup_recovery_keep_original_readable_and_produce_new_active_key(
    context, keyring
):
    old = ContentCrypto(keyring).encrypt(b"restore this data", context)
    backup = keyring.to_json()
    rotated_keys = keyring.with_new_active_key("key-new")
    crypto = ContentCrypto(rotated_keys)
    assert crypto.decrypt(old, context) == b"restore this data"
    replacement = crypto.rotate(old, context)
    assert json.loads(replacement)["key_id"] == "key-new"
    new_only = ContentCrypto(ContentKeyring("key-new", {"key-new": rotated_keys.key("key-new")}))
    assert new_only.decrypt(replacement, context) == b"restore this data"
    with pytest.raises(AppError):
        new_only.decrypt(old, context)
    restored_old = ContentCrypto(ContentKeyring.from_json(backup))
    assert restored_old.decrypt(old, context) == b"restore this data"
    with pytest.raises(AppError):
        restored_old.decrypt(replacement, context)
    damaged = json.loads(old)
    damaged["ciphertext"] = "AAAA"
    with pytest.raises(AppError):
        crypto.rotate(json.dumps(damaged), context)


def test_size_limits_cover_full_ten_mib_document_and_do_not_fit_existing_title_field(
    context, keyring
):
    crypto = ContentCrypto(keyring)
    payload = b"x" * MAX_PLAINTEXT_BYTES
    encrypted = crypto.encrypt(payload, context)
    assert crypto.decrypt(encrypted, context) == payload
    assert len(encrypted.encode("ascii")) < 16777215  # MySQL MEDIUMBLOB/MEDIUMTEXT byte ceiling
    assert len(crypto.encrypt("🙂".encode() * 200, context)) > 200
    with pytest.raises(AppError) as large:
        crypto.encrypt(payload + b"x", context)
    assert large.value.code == 42231
    with pytest.raises(AppError):
        crypto.encrypt("not bytes", context)


@pytest.mark.parametrize(
    "field,value",
    [
        ("owner_id", "not-a-uuid"),
        ("object_id", ""),
        ("revision", "../x"),
        ("field_name", "a/b"),
        ("object_type", None),
    ],
)
def test_context_rejects_invalid_identifiers_before_crypto(field, value, context):
    with pytest.raises(AppError):
        replace(context, **{field: value})
