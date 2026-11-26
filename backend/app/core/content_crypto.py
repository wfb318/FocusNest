"""Versioned envelope encryption for future protected storage; no business I/O here."""

import base64
import binascii
import hmac
import json
import os
import re
from dataclasses import asdict, dataclass
from functools import lru_cache
from uuid import UUID

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.keywrap import InvalidUnwrap, aes_key_unwrap, aes_key_wrap

from app.core.config import get_settings
from app.core.content_keyring import (
    KEY_ID,
    ContentKeyring,
    KeyringError,
    decode_base64,
    load_keyring,
    unique_object,
)
from app.core.exceptions import AppError

MAX_PLAINTEXT_BYTES = 10 * 1024 * 1024
MAX_ENVELOPE_BYTES = 4 * ((MAX_PLAINTEXT_BYTES + 16 + 2) // 3) + 4096
HEADER = {"version": 1, "algorithm": "A256GCM", "key_wrap": "A256KW"}
FIELDS = {*HEADER, "key_id", "wrapped_key", "nonce", "ciphertext"}
TOKEN = re.compile(r"[a-z][a-z0-9_]{0,31}\Z")


def invalid_ciphertext() -> AppError:
    return AppError(422, 42230, "Protected content is invalid or could not be authenticated")


def canonical_json(value: dict) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


@dataclass(frozen=True)
class ContentContext:
    owner_id: str
    object_type: str
    object_id: str
    field_name: str
    revision: str

    def __post_init__(self):
        try:
            ids = (self.owner_id, self.object_id, self.revision)
            if any(not isinstance(value, str) or str(UUID(value)) != value for value in ids):
                raise ValueError()
            if any(
                not isinstance(value, str) or not TOKEN.fullmatch(value)
                for value in (self.object_type, self.field_name)
            ):
                raise ValueError()
        except (ValueError, TypeError, AttributeError):
            raise invalid_ciphertext() from None


def _aad(header: dict, context: ContentContext) -> bytes:
    # Context comes from an authorized DB row, never from an untrusted envelope.
    return canonical_json(
        {"domain": "focusnest/content", "envelope": header, "context": asdict(context)}
    ).encode("ascii")


def _parse(envelope: str) -> dict:
    try:
        if not isinstance(envelope, str) or len(envelope) > MAX_ENVELOPE_BYTES:
            raise ValueError()
        data = json.loads(envelope, object_pairs_hook=unique_object)
        if (
            not isinstance(data, dict)
            or set(data) != FIELDS
            or type(data["version"]) is not int
            or any(data[k] != v for k, v in HEADER.items())
            or not isinstance(data["key_id"], str)
            or not KEY_ID.fullmatch(data["key_id"])
        ):
            raise ValueError()
        for name, minimum, maximum in (
            ("nonce", 12, 12),
            ("wrapped_key", 40, 40),
            ("ciphertext", 16, MAX_PLAINTEXT_BYTES + 16),
        ):
            value = data[name]
            if not isinstance(value, str) or len(value) > 4 * ((maximum + 2) // 3):
                raise ValueError()
            if not minimum <= len(decode_base64(value)) <= maximum:
                raise ValueError()
        return data
    except (ValueError, TypeError, UnicodeError, binascii.Error, RecursionError):
        raise invalid_ciphertext() from None


class ContentCrypto:
    def __init__(self, keyring: ContentKeyring):
        self._keyring = keyring

    def encrypt(self, plaintext: bytes, context: ContentContext) -> str:
        if not isinstance(plaintext, bytes) or len(plaintext) > MAX_PLAINTEXT_BYTES:
            raise AppError(422, 42231, "Protected content exceeds its supported size or type")
        data_key = AESGCM.generate_key(bit_length=256)
        header = {
            **HEADER,
            "key_id": self._keyring.active_key_id,
            "wrapped_key": base64.b64encode(
                aes_key_wrap(self._keyring.key(self._keyring.active_key_id), data_key)
            ).decode("ascii"),
            "nonce": base64.b64encode(os.urandom(12)).decode("ascii"),
        }
        ciphertext = AESGCM(data_key).encrypt(
            decode_base64(header["nonce"]), plaintext, _aad(header, context)
        )
        return canonical_json(
            {**header, "ciphertext": base64.b64encode(ciphertext).decode("ascii")}
        )

    def decrypt(self, envelope: str, context: ContentContext) -> bytes:
        data = _parse(envelope)
        key = self._keyring.key(data["key_id"])  # missing old key fails closed, no key guessing
        try:
            data_key = aes_key_unwrap(key, decode_base64(data["wrapped_key"]))
            header = {k: v for k, v in data.items() if k != "ciphertext"}
            return AESGCM(data_key).decrypt(
                decode_base64(data["nonce"]),
                decode_base64(data["ciphertext"]),
                _aad(header, context),
            )
        except (InvalidTag, InvalidUnwrap, ValueError):
            raise invalid_ciphertext() from None

    def rotate(self, envelope: str, context: ContentContext) -> str:
        """Verify then create a fresh envelope with the active KEK; caller persists with CAS."""
        plaintext = self.decrypt(envelope, context)
        result = self.encrypt(plaintext, context)
        if not hmac.compare_digest(self.decrypt(result, context), plaintext):
            raise invalid_ciphertext()
        return result


@lru_cache
def get_content_crypto() -> ContentCrypto:
    settings = get_settings()
    keyring = load_keyring(settings.content_keyring_file)
    signing_secret = settings.jwt_secret.get_secret_value().encode("utf-8")
    forbidden = [signing_secret]
    try:
        forbidden.append(decode_base64(signing_secret.decode("utf-8")))
    except (ValueError, binascii.Error):
        pass
    for decode in (
        lambda value: base64.b64decode(
            value + b"=" * (-len(value) % 4), altchars=b"-_", validate=True
        ),
        lambda value: bytes.fromhex(value.decode("ascii")),
    ):
        try:
            forbidden.append(decode(signing_secret))
        except (ValueError, UnicodeError, binascii.Error):
            pass
    if any(
        hmac.compare_digest(key, other) for key in keyring._keys.values() for other in forbidden
    ):
        raise KeyringError()
    return ContentCrypto(keyring)
