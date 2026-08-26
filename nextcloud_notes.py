#!/usr/bin/env python3
"""A small GTK4 desktop client for Nextcloud Notes."""

from __future__ import annotations

import base64
import json
import os
import subprocess
import threading
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gdk, Gio, GLib, Gtk


APP_ID = "io.github.jakewaynemurray.omarchy-app-nextcloud-notes"
KEYRING_ID = "omarchy-app-nextcloud-notes"
CONFIG_FILE = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "omarchy" / "nextcloud-notes-app.json"
MAX_NOTES = 500


class NotesError(RuntimeError):
    pass


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
    CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    CONFIG_FILE.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    os.chmod(CONFIG_FILE, 0o600)


def keyring(*args: str, stdin: str | None = None) -> subprocess.CompletedProcess:
    try:
        return subprocess.run(["secret-tool", *args], input=stdin, text=True,
                              capture_output=True, timeout=15, check=False)
    except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
        raise NotesError("The desktop keyring is unavailable. Install secret-tool and try again.") from exc


def store_password(url: str, username: str, password: str) -> None:
    result = keyring("store", "--label=Nextcloud Notes", "service", KEYRING_ID,
                     "url", url, "username", username, stdin=password)
    if result.returncode:
        raise NotesError(result.stderr.strip() or "Could not store the password in the desktop keyring.")


def lookup_password(url: str, username: str) -> str:
    result = keyring("lookup", "service", KEYRING_ID, "url", url, "username", username)
    if result.returncode or not result.stdout:
        raise NotesError("Password not found. Sign in again to reconnect.")
    return result.stdout.rstrip("\n")


class NotesApi:
    def __init__(self, url: str, username: str, password: str):
        self.url, self.username, self.password = url, username, password

    def request(self, path: str = "notes", method: str = "GET", body: dict | None = None,
                etag: str = "") -> object:
        token = base64.b64encode(f"{self.username}:{self.password}".encode()).decode()
        headers = {"Accept": "application/json", "Authorization": f"Basic {token}",
                   "User-Agent": "Omarchy-App-Nextcloud-Notes/1.0"}
        data = None
        if body is not None:
            headers["Content-Type"] = "application/json"
            data = json.dumps(body, ensure_ascii=False).encode()
        if etag:
            headers["If-Match"] = etag
        request = urllib.request.Request(
            f"{self.url}/index.php/apps/notes/api/v1/{path.lstrip('/')}",
            data=data, headers=headers, method=method)
        try:
            with urllib.request.urlopen(request, timeout=15) as response:
                return json.loads(response.read(8 * 1024 * 1024).decode("utf-8"))
        except urllib.error.HTTPError as exc:
            if exc.code == 404:
                return self.request_legacy(path, method, body, etag)
            if exc.code in {401, 403}:
                raise NotesError("Nextcloud rejected the credentials or note access.") from exc
            raise NotesError(f"Nextcloud returned HTTP {exc.code}.") from exc
        except (urllib.error.URLError, TimeoutError) as exc:
            raise NotesError(f"Could not reach Nextcloud: {getattr(exc, 'reason', exc)}") from exc
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            raise NotesError("Nextcloud returned invalid data.") from exc

    def request_legacy(self, path: str, method: str, body: dict | None, etag: str) -> object:
        token = base64.b64encode(f"{self.username}:{self.password}".encode()).decode()
        headers = {"Accept": "application/json", "Authorization": f"Basic {token}",
                   "User-Agent": "Omarchy-App-Nextcloud-Notes/1.0"}
        if body is not None:
            headers["Content-Type"] = "application/json"
        if etag:
            headers["If-Match"] = etag
        data = json.dumps(body).encode() if body is not None else None
        request = urllib.request.Request(
            f"{self.url}/index.php/apps/notes/api/0.2/{path.lstrip('/')}",
            data=data, headers=headers, method=method)
        try:
            with urllib.request.urlopen(request, timeout=15) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            if exc.code in {401, 403}:
                raise NotesError("Nextcloud rejected the credentials or note access.") from exc
            raise NotesError(f"Nextcloud returned HTTP {exc.code}.") from exc

    def list_notes(self) -> list[dict]:
        notes = self.request("notes?chunkSize=500")
        if not isinstance(notes, list):
            raise NotesError("Nextcloud returned an invalid notes list.")
        if len(notes) > MAX_NOTES:
            raise NotesError(f"This account has more than {MAX_NOTES} notes.")
        return [self.normalize(note) for note in notes if isinstance(note, dict)]

    def get_note(self, note_id: int) -> dict:
        note = self.request(f"notes/{urllib.parse.quote(str(note_id), safe='')}")
        if not isinstance(note, dict):
            raise NotesError("Nextcloud returned an invalid note.")
        return self.normalize(note)

    def save_note(self, note: dict) -> dict:
        payload = {"title": note["title"], "content": note["content"], "category": note["category"]}
        if note.get("id"):
            result = self.request(f"notes/{note['id']}", "PUT", payload, note.get("etag", ""))
        else:
            result = self.request("notes", "POST", payload)
        if not isinstance(result, dict):
            raise NotesError("Nextcloud returned an invalid saved note.")
        return self.normalize(result)

    @staticmethod
    def normalize(note: dict) -> dict:
        return {"id": int(note.get("id", 0)), "title": str(note.get("title") or "Untitled note"),
                "content": str(note.get("content") or ""), "category": str(note.get("category") or ""),
                "etag": str(note.get("etag") or ""), "favorite": bool(note.get("favorite", False)),
                "readonly": bool(note.get("readonly", False))}


class NotesWindow(Adw.ApplicationWindow):
    def __init__(self, app: Adw.Application):
        super().__init__(application=app, title="Nextcloud Notes", default_width=1100, default_height=760)
        self.api: NotesApi | None = None
        self.notes: list[dict] = []
        self.current_note: dict | None = None
        self.toast_overlay = Adw.ToastOverlay()
        self.set_content(self.toast_overlay)
        self.css()
        self.build_login()

    def css(self):
        provider = Gtk.CssProvider()
        provider.load_from_data(b"""
        .omarchy-title { font-size: 28px; font-weight: 700; }
        .omarchy-subtitle { color: alpha(@window_fg_color, .65); }
        .note-row { padding: 12px 16px; }
        .note-row-title { font-weight: 700; }
        .editor-title { font-size: 25px; font-weight: 700; }
        .danger { color: @error_color; }
        """)
        Gtk.StyleContext.add_provider_for_display(Gdk.Display.get_default(), provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)

    def show_toast(self, message: str) -> None:
        self.toast_overlay.add_toast(Adw.Toast.new(message))

    def header(self, title: str, back: bool = False) -> Adw.HeaderBar:
        header = Adw.HeaderBar()
        header.set_title_widget(Gtk.Label(label=title))
        if back:
            button = Gtk.Button(icon_name="go-previous-symbolic", tooltip_text="Back to notes")
            button.connect("clicked", lambda *_: self.show_list())
            header.pack_start(button)
        return header

    def build_login(self) -> None:
        page = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        page.append(self.header("Nextcloud Notes"))
        center = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=14)
        center.set_halign(Gtk.Align.CENTER)
        center.set_valign(Gtk.Align.CENTER)
        center.set_size_request(420, -1)
        title = Gtk.Label(label="Connect your notes", css_classes=["omarchy-title"])
        subtitle = Gtk.Label(label="A focused, lightweight Nextcloud Notes app", css_classes=["omarchy-subtitle"])
        self.url = Gtk.Entry(placeholder_text="https://cloud.example.com or http://cloud.local")
        self.user = Gtk.Entry(placeholder_text="Username")
        self.password = Gtk.PasswordEntry(placeholder_text="Password or app password", show_peek_icon=True)
        self.login_button = Gtk.Button(label="Sign in", css_classes=["suggested-action"])
        self.login_button.connect("clicked", self.login)
        self.password.connect("activate", self.login)
        for widget in (title, subtitle, self.url, self.user, self.password, self.login_button):
            center.append(widget)
        page.append(center)
        self.toast_overlay.set_child(page)
        self.url.grab_focus()

    def login(self, *_args) -> None:
        try:
            url = normalize_url(self.url.get_text())
            username = self.user.get_text().strip()
            password = self.password.get_text()
            if not username or not password:
                raise NotesError("Username and password are required.")
            self.login_button.set_sensitive(False)
            self.login_button.set_label("Connecting…")
        except NotesError as exc:
            self.show_toast(str(exc))
            return
        self.run_async(lambda: self.make_api(url, username, password).list_notes(),
                       lambda notes: self.finish_login(url, username, password, notes))

    def make_api(self, url: str, username: str, password: str) -> NotesApi:
        return NotesApi(url, username, password)

    def finish_login(self, url: str, username: str, password: str, notes: list[dict]) -> None:
        try:
            store_password(url, username, password)
            write_config({"url": url, "username": username})
        except NotesError as exc:
            self.login_button.set_sensitive(True)
            self.login_button.set_label("Sign in")
            self.show_toast(str(exc))
            return
        self.api = NotesApi(url, username, password)
        self.notes = notes
        self.show_list()

    def show_list(self) -> None:
        if not self.api:
            return
        page = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        header = self.header("Nextcloud Notes")
        refresh = Gtk.Button(icon_name="view-refresh-symbolic", tooltip_text="Refresh notes")
        refresh.connect("clicked", lambda *_: self.refresh())
        logout = Gtk.Button(label="Sign out")
        logout.connect("clicked", lambda *_: self.sign_out())
        header.pack_end(logout)
        header.pack_end(refresh)
        page.append(header)
        content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        content.set_margin_top(18); content.set_margin_bottom(18); content.set_margin_start(24); content.set_margin_end(24)
        self.search = Gtk.SearchEntry(placeholder_text="Filter notes…")
        self.search.connect("search-changed", lambda *_: self.populate_notes())
        content.append(self.search)
        self.note_list = Gtk.ListBox(selection_mode=Gtk.SelectionMode.SINGLE, css_classes=["boxed-list"])
        self.note_list.connect("row-activated", self.open_note)
        scroll = Gtk.ScrolledWindow(vexpand=True)
        scroll.set_child(self.note_list)
        content.append(scroll)
        page.append(content)
        self.toast_overlay.set_child(page)
        self.populate_notes()

    def populate_notes(self) -> None:
        while row := self.note_list.get_row_at_index(0):
            self.note_list.remove(row)
        query = self.search.get_text().casefold()
        for note in sorted(self.notes, key=lambda n: (not n["favorite"], n["title"].casefold())):
            if query and query not in f"{note['title']} {note['category']}".casefold():
                continue
            row = Gtk.ListBoxRow()
            box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=3, css_classes=["note-row"])
            box.append(Gtk.Label(label=("★ " if note["favorite"] else "") + note["title"], xalign=0, css_classes=["note-row-title"]))
            box.append(Gtk.Label(label=note["category"] or "Uncategorized", xalign=0, css_classes=["omarchy-subtitle"]))
            row.set_child(box); row.note = note
            self.note_list.append(row)

    def open_note(self, _list, row) -> None:
        self.run_async(lambda: self.api.get_note(row.note["id"]), self.show_editor)

    def show_editor(self, note: dict) -> None:
        self.current_note = note
        page = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        header = self.header("Edit note" if not note["readonly"] else "View note", back=True)
        self.save_button = Gtk.Button(label="Save", css_classes=["suggested-action"])
        self.save_button.set_sensitive(not note["readonly"])
        self.save_button.connect("clicked", self.save_note)
        header.pack_end(self.save_button)
        page.append(header)
        editor = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        editor.set_margin_top(22); editor.set_margin_bottom(22); editor.set_margin_start(32); editor.set_margin_end(32)
        self.title = Gtk.Entry(text=note["title"], css_classes=["editor-title"])
        self.category = Gtk.Entry(text=note["category"], placeholder_text="Category (optional)")
        self.body = Gtk.TextView(wrap_mode=Gtk.WrapMode.WORD_CHAR, vexpand=True, top_margin=12, bottom_margin=12, left_margin=12, right_margin=12)
        self.body.get_buffer().set_text(note["content"])
        for widget in (self.title, self.category): widget.set_sensitive(not note["readonly"])
        self.body.set_editable(not note["readonly"])
        body_scroll = Gtk.ScrolledWindow(vexpand=True); body_scroll.set_child(self.body)
        editor.append(self.title); editor.append(self.category); editor.append(body_scroll)
        page.append(editor)
        self.toast_overlay.set_child(page)
        self.body.grab_focus()

    def save_note(self, *_args) -> None:
        if not self.api or not self.current_note: return
        start, end = self.body.get_buffer().get_bounds()
        note = {**self.current_note, "title": self.title.get_text(), "category": self.category.get_text(),
                "content": self.body.get_buffer().get_text(start, end, False)}
        self.save_button.set_sensitive(False)
        self.run_async(lambda: self.api.save_note(note), self.finish_save)

    def finish_save(self, note: dict) -> None:
        self.current_note = note
        self.notes = [note if n["id"] == note["id"] else n for n in self.notes]
        self.save_button.set_sensitive(True)
        self.show_toast("Note saved")

    def refresh(self) -> None:
        if self.api: self.run_async(self.api.list_notes, lambda notes: (setattr(self, "notes", notes), self.populate_notes()))

    def sign_out(self) -> None:
        self.api = None
        self.notes = []
        self.build_login()

    def run_async(self, work, success) -> None:
        def worker():
            try:
                result = work()
                GLib.idle_add(success, result)
            except NotesError as exc:
                GLib.idle_add(self.show_toast, str(exc))
            except Exception as exc:
                GLib.idle_add(self.show_toast, f"Unexpected error: {exc}")
        threading.Thread(target=worker, daemon=True).start()


class App(Adw.Application):
    def __init__(self):
        super().__init__(application_id=APP_ID, flags=Gio.ApplicationFlags.DEFAULT_FLAGS)

    def do_activate(self):
        window = self.props.active_window or NotesWindow(self)
        window.present()


if __name__ == "__main__":
    raise SystemExit(App().run())
