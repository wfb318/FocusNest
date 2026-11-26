"""Update schedule choices on the existing Ubuntu FocusNest server."""

import json
import os
import shutil
import subprocess
import sys
import tarfile
import tempfile
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path("/srv/focusnest")
PACKAGE = Path(__file__).resolve().parent
SERVICE_FILE = Path("backend/app/services/schedule_templates.py")


def command(*args):
    subprocess.run(args, check=True)


def install_file(source, target, owner):
    temporary = target.with_name("." + target.name + ".schedule-options-update")
    shutil.copyfile(source, temporary)
    os.chown(temporary, owner.st_uid, owner.st_gid)
    os.chmod(temporary, 0o644)
    temporary.replace(target)


def healthy():
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    for _ in range(15):
        try:
            with opener.open(
                "http://127.0.0.1:8000/api/v1/health?check_database=true", timeout=3
            ) as response:
                if json.load(response).get("data", {}).get("database") == "connected":
                    return True
        except (OSError, ValueError):
            pass
        time.sleep(1)
    return False


def main():
    if not hasattr(os, "geteuid") or os.geteuid() != 0:
        raise SystemExit("Run with sudo and the server virtual-environment Python.")
    os.umask(0o077)
    for path in (
        ROOT / SERVICE_FILE,
        ROOT / "frontend/index.html",
        ROOT / "backend/alembic/versions/0019_admin_and_presence.py",
        PACKAGE / SERVICE_FILE,
        PACKAGE / "frontend/index.html",
    ):
        if not path.is_file():
            raise SystemExit(f"Missing update input: {path}")
    if not (PACKAGE / "frontend/assets").is_dir():
        raise SystemExit("Built frontend assets are missing.")
    if subprocess.run(["systemctl", "is-active", "--quiet", "focusnest"]).returncode:
        raise SystemExit("The existing focusnest service must be healthy before updating.")
    if not healthy():
        raise SystemExit("Existing backend health check failed; no code was changed.")
    backup_root = Path("/var/backups/focusnest")
    backup_root.mkdir(parents=True, exist_ok=True)
    os.chmod(backup_root, 0o700)
    backup = Path(
        tempfile.mkdtemp(
            prefix="schedule-options-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ-"),
            dir=backup_root,
        )
    )
    shutil.copyfile(ROOT / SERVICE_FILE, backup / "schedule_templates.py")
    shutil.copyfile(ROOT / "frontend/index.html", backup / "index.html")
    with tarfile.open(backup / "previous-code.tar.gz", "x:gz") as archive:
        archive.add(ROOT / SERVICE_FILE, arcname=str(SERVICE_FILE))
        archive.add(ROOT / "frontend", arcname="frontend")
    print(f"Code backup: {backup}", flush=True)
    backend_owner = (ROOT / SERVICE_FILE).stat()
    frontend_owner = (ROOT / "frontend").stat()
    stopped = False
    try:
        command("systemctl", "stop", "focusnest")
        stopped = True
        install_file(PACKAGE / SERVICE_FILE, ROOT / SERVICE_FILE, backend_owner)
        for source in (PACKAGE / "frontend/assets").iterdir():
            if not source.is_file():
                raise RuntimeError("Unexpected frontend asset directory")
            install_file(source, ROOT / "frontend/assets" / source.name, frontend_owner)
        command("systemctl", "start", "focusnest")
        if not healthy():
            raise RuntimeError("Updated backend health check failed")
        install_file(PACKAGE / "frontend/index.html", ROOT / "frontend/index.html", frontend_owner)
        print("SCHEDULE_OPTIONS_READY: backend healthy, frontend installed.")
        print("Database schema and existing administrator accounts were not changed.")
        return 0
    except (OSError, RuntimeError, subprocess.SubprocessError, KeyboardInterrupt) as error:
        if stopped:
            install_file(backup / "schedule_templates.py", ROOT / SERVICE_FILE, backend_owner)
            install_file(backup / "index.html", ROOT / "frontend/index.html", frontend_owner)
            subprocess.run(["systemctl", "restart", "focusnest"], check=False)
        print(f"Update stopped ({type(error).__name__}); previous code restored: {backup}")
        return 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, tarfile.TarError, EOFError):
        print(
            "Update preparation failed. Check server paths and available disk space.",
            file=sys.stderr,
        )
        raise SystemExit(1)
