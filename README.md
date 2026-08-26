# Omarchy App: Nextcloud Notes

A focused, lightweight Qt/QML desktop client for Nextcloud Notes. It
uses the same dark, compact visual language as the Omarchy plugin, but gives
notes a full-sized window for reading and editing.

## Features

- Login with a server URL, username, and password or app password.
- Supports both `http://` and `https://` server URLs. HTTP is useful for a
  trusted local network; HTTPS is recommended on untrusted networks.
- Searchable notes list with favorite indicators.
- Full note view and editing with optimistic concurrency via `ETag`.
- Markdown-first notes: switch between raw Markdown editing and rendered
  Markdown preview in the note editor.
- Loads the last successful notes list from a local cache immediately on startup;
  use Refresh for an explicit server reload.
- Edited notes are pushed automatically about every 30 seconds while open, or
  immediately with Save.
- Password stored in the desktop keyring using `secret-tool`; URL and username
  are stored in `~/.config/omarchy/nextcloud-notes-app/config.json`; cached notes live
  under `~/.config/omarchy/nextcloud-notes-app/`.
- Uses Quickshell, Qt Quick Controls, and the installed Omarchy `qs.Commons`
  and `qs.Ui` components; Python is only a small JSON-line API bridge.

## Run locally

On Omarchy/Arch, install the runtime dependencies if needed:

```bash
sudo pacman -S quickshell python libsecret
./run.sh
```

The Nextcloud Notes app API is enabled by default in current Notes releases.
The client tries API v1 first and falls back to v0.2 for older servers.

## Install locally

```bash
install -Dm755 App.qml nextcloud_client.py run.sh ~/.local/lib/omarchy-app-nextcloud-notes/
sed "s#^Exec=.*#Exec=$HOME/.local/lib/omarchy-app-nextcloud-notes/run.sh#" \
  nextcloud-notes.desktop > ~/.local/share/applications/nextcloud-notes.desktop
```

## Development

```bash
python3 -m py_compile nextcloud_client.py
python3 -m unittest discover -v
```

## License

MIT
