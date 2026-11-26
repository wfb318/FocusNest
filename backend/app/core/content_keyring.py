"""Platform-owned content keys. No automatic generation, logging, or plaintext fallback."""

import base64
import binascii
import json
import os
import re
import stat
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from types import MappingProxyType
from typing import Mapping

from app.core.config import BACKEND_DIR
from app.core.exceptions import AppError

KEY_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,63}\Z")
MAX_KEYRING_BYTES = 65536
MAX_KEYS = 32
PROJECT_DIR = BACKEND_DIR.parent.resolve()


class KeyringError(AppError):
    def __init__(self):
        super().__init__(503, 50330, "Content encryption keys are unavailable or invalid")


def unique_object(pairs):
    result = {}
    for name, value in pairs:
        if name in result:
            raise ValueError("Duplicate JSON field")
        result[name] = value
    return result


def decode_base64(value: str) -> bytes:
    if not isinstance(value, str):
        raise ValueError("Invalid encoding")
    data = base64.b64decode(value, validate=True)
    if base64.b64encode(data).decode("ascii") != value:
        raise ValueError("Noncanonical encoding")
    return data


@dataclass(frozen=True)
class ContentKeyring:
    active_key_id: str
    _keys: Mapping[str, bytes] = field(repr=False)

    def __post_init__(self):
        keys = dict(self._keys)
        if (
            not 1 <= len(keys) <= MAX_KEYS
            or self.active_key_id not in keys
            or any(not isinstance(k, str) or not KEY_ID.fullmatch(k) for k in keys)
            or any(not isinstance(v, bytes) or len(v) != 32 for v in keys.values())
            or len(set(keys.values())) != len(keys)
        ):
            raise KeyringError()
        object.__setattr__(self, "_keys", MappingProxyType(keys))

    @classmethod
    def from_json(cls, raw: bytes) -> "ContentKeyring":
        try:
            if len(raw) > MAX_KEYRING_BYTES:
                raise ValueError()
            data = json.loads(raw.decode("utf-8"), object_pairs_hook=unique_object)
            if (
                not isinstance(data, dict)
                or set(data) != {"version", "active_key_id", "keys"}
                or type(data["version"]) is not int
                or data["version"] != 1
                or not isinstance(data["active_key_id"], str)
                or not isinstance(data["keys"], dict)
                or not 1 <= len(data["keys"]) <= MAX_KEYS
            ):
                raise ValueError()
            keys = {key: decode_base64(value) for key, value in data["keys"].items()}
            return cls(data["active_key_id"], keys)
        except (ValueError, TypeError, UnicodeError, binascii.Error, RecursionError):
            raise KeyringError() from None

    def key(self, key_id: str) -> bytes:
        try:
            return self._keys[key_id]
        except KeyError:
            raise KeyringError() from None

    def to_json(self) -> bytes:
        """For restricted-file administration only. Never include this in responses or logs."""
        return (
            json.dumps(
                {
                    "version": 1,
                    "active_key_id": self.active_key_id,
                    "keys": {k: base64.b64encode(v).decode("ascii") for k, v in self._keys.items()},
                },
                indent=2,
            ).encode("ascii")
            + b"\n"
        )

    def with_new_active_key(self, key_id: str) -> "ContentKeyring":
        if not isinstance(key_id, str) or not KEY_ID.fullmatch(key_id) or key_id in self._keys:
            raise KeyringError()
        return ContentKeyring(key_id, {**self._keys, key_id: os.urandom(32)})


def external_keyring_path(path: Path) -> Path:
    try:
        if not path.is_absolute() or path.is_symlink():
            raise KeyringError()
        resolved = path.resolve()
        if resolved.is_relative_to(PROJECT_DIR):
            raise KeyringError()
        return resolved
    except (OSError, ValueError, RuntimeError):
        raise KeyringError() from None


def _windows_command(executable: str, *args: str, env=None) -> str:
    binary = Path(os.environ.get("SystemRoot", r"C:\Windows")) / "System32" / executable
    try:
        result = subprocess.run(
            [str(binary), *args],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=True,
            timeout=15,
            env=env,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        return result.stdout
    except (OSError, subprocess.SubprocessError):
        raise KeyringError() from None


def _windows_sid() -> str:
    match = re.search(
        r"S-1-\d+(?:-\d+)+", _windows_command("whoami.exe", "/user", "/fo", "csv", "/nh")
    )
    if not match:
        raise KeyringError()
    return match[0]


def check_file_permissions(path: Path, info: os.stat_result) -> None:
    if not stat.S_ISREG(info.st_mode):
        raise KeyringError()
    if os.name != "nt":
        if info.st_mode & 0o077 or info.st_uid not in (os.geteuid(), 0):
            raise KeyringError()
        return
    script = (
        "$ErrorActionPreference='Stop';"
        "$a=[System.IO.File]::GetAccessControl($env:FOCUSNEST_CONTENT_KEYFILE);"
        "$s=[System.Security.Principal.SecurityIdentifier];"
        "$r=@($a.GetAccessRules($true,$true,$s)|"
        "Where-Object {$_.AccessControlType -eq 'Allow'}|"
        "ForEach-Object {$_.IdentityReference.Value});"
        "@{owner=$a.GetOwner($s).Value;protected=$a.AreAccessRulesProtected;allowed=$r}"
        "|ConvertTo-Json -Compress"
    )
    environment = {**os.environ, "FOCUSNEST_CONTENT_KEYFILE": str(path)}
    try:
        acl = json.loads(
            _windows_command(
                r"WindowsPowerShell\v1.0\powershell.exe",
                "-NoProfile",
                "-NonInteractive",
                "-Command",
                script,
                env=environment,
            )
        )
        allowed = {_windows_sid(), "S-1-5-18", "S-1-5-32-544"}  # current user, SYSTEM, admins
        if (
            acl.get("protected") is not True
            or acl.get("owner") not in allowed
            or not acl.get("allowed")
            or any(sid not in allowed for sid in acl["allowed"])
        ):
            raise KeyringError()
    except (ValueError, TypeError, AttributeError):
        raise KeyringError() from None


def load_keyring(path: Path | None) -> ContentKeyring:
    if path is None:
        raise KeyringError()
    path = external_keyring_path(path)
    try:
        original = path.stat()
        check_file_permissions(path, original)
        flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_BINARY", 0)
        with os.fdopen(os.open(path, flags), "rb") as stream:
            info = os.fstat(stream.fileno())
            if (
                not os.path.samestat(original, info)
                or not stat.S_ISREG(info.st_mode)
                or info.st_nlink != 1
                or info.st_size > MAX_KEYRING_BYTES
            ):
                raise KeyringError()
            raw = stream.read(MAX_KEYRING_BYTES + 1)
            latest = os.fstat(stream.fileno())
            if (latest.st_mtime_ns, latest.st_size) != (info.st_mtime_ns, info.st_size):
                raise KeyringError()
        return ContentKeyring.from_json(raw)
    except OSError:
        raise KeyringError() from None


def write_new_keyring(path: Path, keyring: ContentKeyring) -> None:
    """Create only. Apply restrictive permissions before writing any secret bytes."""
    path = external_keyring_path(path)
    try:
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_BINARY", 0)
        descriptor = os.open(path, flags, 0o600)
        with os.fdopen(descriptor, "wb") as stream:
            if os.name == "nt":
                sid = _windows_sid()
                _windows_command(
                    "icacls.exe",
                    str(path),
                    "/inheritance:r",
                    "/grant:r",
                    f"*{sid}:(F)",
                    "*S-1-5-18:(F)",
                )
            check_file_permissions(path, os.fstat(stream.fileno()))
            stream.write(keyring.to_json())
            stream.flush()
            os.fsync(stream.fileno())
        restored = load_keyring(path)
        if restored.to_json() != keyring.to_json():
            raise KeyringError()
    except OSError:
        raise KeyringError() from None
