#!/usr/bin/env python3
"""JSON-line bridge for the Omarchy Qt/QML Nextcloud Notes app."""

from __future__ import annotations

import base64
import json
import os
import subprocess
import sys
import tempfile
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

APP_ID = "omarchy-app-nextcloud-notes"
CONFIG_DIR = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "omarchy" / "nextcloud-notes-app"
CONFIG_FILE = CONFIG_DIR / "config.json"
CACHE_FILE = CONFIG_DIR / "notes-cache.json"


class NotesError(RuntimeError):
    pass


def emit(data: dict) -> None:
    print(json.dumps(data, ensure_ascii=False, separators=(",", ":")))


def normalize_url(value: str) -> str:
    parsed = urllib.parse.urlparse(value.strip().rstrip("/"))
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise NotesError("Enter a valid http:// or https:// Nextcloud URL.")
    if "/index.php" in parsed.path:
        parsed = parsed._replace(path=parsed.path.split("/index.php", 1)[0])
    return parsed._replace(params="", query="", fragment="").geturl().rstrip("/")


def read_config() -> dict:
    try:
        data = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return {}


def write_config(data: dict) -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True, mode=0o700)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=CONFIG_DIR, delete=False) as handle:
        json.dump(data, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
        temporary = handle.name
    os.chmod(temporary, 0o600)
    os.replace(temporary, CONFIG_FILE)


def write_cache(notes: list[dict]) -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True, mode=0o700)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=CONFIG_DIR, delete=False) as handle:
        json.dump({"notes": notes}, handle, ensure_ascii=False, separators=(",", ":"))
        handle.write("\n")
        temporary = handle.name
    os.chmod(temporary, 0o600)
    os.replace(temporary, CACHE_FILE)


def update_cache(note: dict) -> None:
    try:
        cached = json.loads(CACHE_FILE.read_text(encoding="utf-8"))
        notes = cached.get("notes", []) if isinstance(cached, dict) else []
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        notes = []
    notes = [item for item in notes if isinstance(item, dict) and item.get("id") != note.get("id")]
    notes.append(note)
    write_cache(notes)


def keyring(*args: str, stdin: str | None = None) -> subprocess.CompletedProcess:
    try:
        return subprocess.run(["secret-tool", *args], input=stdin, text=True, capture_output=True,
                              timeout=15, check=False)
    except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
        raise NotesError("The desktop keyring is unavailable. Install secret-tool and try again.") from exc


def password_for(url: str, username: str) -> str:
    result = keyring("lookup", "service", APP_ID, "url", url, "username", username)
    if result.returncode or not result.stdout:
        raise NotesError("Password not found. Sign in again to reconnect.")
    return result.stdout.rstrip("\n")


def store_password(url: str, username: str, password: str) -> None:
    result = keyring("store", "--label=Nextcloud Notes", "service", APP_ID,
                     "url", url, "username", username, stdin=password)
    if result.returncode:
        raise NotesError(result.stderr.strip() or "Could not store the password in the desktop keyring.")


def request(base: str, username: str, password: str, path: str = "notes", method: str = "GET",
            body: dict | None = None, etag: str = "", version: str = "v1") -> object:
    token = base64.b64encode(f"{username}:{password}".encode()).decode()
    headers = {"Accept": "application/json", "Authorization": f"Basic {token}",
               "User-Agent": "Omarchy-App-Nextcloud-Notes/1.0"}
    data = None
    if body is not None:
        headers["Content-Type"] = "application/json"
        data = json.dumps(body, ensure_ascii=False).encode()
    if etag:
        headers["If-Match"] = etag
    url = f"{base}/index.php/apps/notes/api/{version}/{path.lstrip('/')}"
    try:
        with urllib.request.urlopen(urllib.request.Request(url, data=data, headers=headers, method=method), timeout=15) as response:
            return json.loads(response.read(8 * 1024 * 1024).decode("utf-8"))
    except urllib.error.HTTPError as exc:
        if exc.code == 404 and version == "v1":
            return request(base, username, password, path, method, body, etag, "0.2")
        if exc.code in {401, 403}:
            raise NotesError("Nextcloud rejected the credentials or note access.") from exc
        raise NotesError(f"Nextcloud returned HTTP {exc.code}.") from exc
    except (urllib.error.URLError, TimeoutError) as exc:
        raise NotesError(f"Could not reach Nextcloud: {getattr(exc, 'reason', exc)}") from exc
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise NotesError("Nextcloud returned invalid data.") from exc


def connection() -> tuple[str, str, str]:
    config = read_config()
    url = normalize_url(str(config.get("url", "")))
    username = str(config.get("username", "")).strip()
    if not username:
        raise NotesError("Nextcloud username is missing.")
    return url, username, password_for(url, username)


def normalize(note: dict) -> dict:
    return {"id": int(note.get("id", 0)), "title": str(note.get("title") or "Untitled note"),
            "content": str(note.get("content") or ""), "category": str(note.get("category") or ""),
            "etag": str(note.get("etag") or ""), "favorite": bool(note.get("favorite", False)),
            "readonly": bool(note.get("readonly", False))}


def main() -> None:
    command = sys.argv[1] if len(sys.argv) > 1 else ""
    try:
        if command == "status":
            config = read_config()
            emit({"ok": True, "configured": bool(config.get("url") and config.get("username")),
                  "url": config.get("url", ""), "username": config.get("username", "")})
        elif command == "configure":
            payload = json.loads(sys.stdin.readline())
            url = normalize_url(str(payload.get("url", "")))
            username = str(payload.get("username", "")).strip()
            password = str(payload.get("password", ""))
            if not username or not password:
                raise NotesError("Username and password are required.")
            notes = request(url, username, password, "notes?chunkSize=1")
            if not isinstance(notes, list):
                raise NotesError("Nextcloud returned an invalid notes list.")
            store_password(url, username, password)
            write_config({"url": url, "username": username})
            emit({"ok": True, "configured": True, "url": url, "username": username})
        elif command == "list":
            base, user, password = connection()
            notes = request(base, user, password, "notes?chunkSize=500")
            if not isinstance(notes, list):
                raise NotesError("Nextcloud returned an invalid notes list.")
            normalized = [normalize(note) for note in notes if isinstance(note, dict)]
            write_cache(normalized)
            emit({"ok": True, "notes": normalized})
        elif command == "cache":
            try:
                cached = json.loads(CACHE_FILE.read_text(encoding="utf-8"))
                notes = cached.get("notes", []) if isinstance(cached, dict) else []
            except (FileNotFoundError, json.JSONDecodeError, OSError):
                notes = []
            if not isinstance(notes, list):
                notes = []
            emit({"ok": True, "cached": CACHE_FILE.exists(), "notes": notes})
        elif command == "get" and len(sys.argv) == 3:
            base, user, password = connection()
            note = request(base, user, password, f"notes/{urllib.parse.quote(sys.argv[2], safe='')}")
            if not isinstance(note, dict):
                raise NotesError("Nextcloud returned an invalid note.")
            emit({"ok": True, "note": normalize(note)})
        elif command == "save":
            payload = json.loads(sys.stdin.readline())
            base, user, password = connection()
            body = {"title": str(payload.get("title", "Untitled note")), "content": str(payload.get("content", ""))}
            note_id = str(payload.get("id", "")).strip()
            path = f"notes/{urllib.parse.quote(note_id, safe='')}" if note_id else "notes"
            method = "PUT" if note_id else "POST"
            note = request(base, user, password, path, method, body, str(payload.get("etag", "")))
            if not isinstance(note, dict):
                raise NotesError("Nextcloud returned an invalid saved note.")
            normalized = normalize(note)
            update_cache(normalized)
            emit({"ok": True, "note": normalized})
        else:
            emit({"ok": False, "error": "Usage: status|configure|list|get ID|save"})
    except (NotesError, json.JSONDecodeError) as exc:
        emit({"ok": False, "error": str(exc) or "Invalid request."})


if __name__ == "__main__":
    main()
