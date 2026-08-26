# Omarchy App: Nextcloud Notes

A focused, lightweight GTK4/Libadwaita desktop client for Nextcloud Notes. It
uses the same dark, compact visual language as the Omarchy plugin, but gives
notes a full-sized window for reading and editing.

## Features

- Login with a server URL, username, and password or app password.
- Supports both `http://` and `https://` server URLs. HTTP is useful for a
  trusted local network; HTTPS is recommended on untrusted networks.
- Searchable notes list with favorite and category indicators.
- Full note view and editing with optimistic concurrency via `ETag`.
- Password stored in the desktop keyring using `secret-tool`; URL and username
  are stored in `~/.config/omarchy/nextcloud-notes-app.json`.
- No runtime dependencies beyond Python 3, GTK4, Libadwaita, and PyGObject.

## Run locally

On Omarchy/Arch, install the runtime dependencies if needed:

```bash
sudo pacman -S python-gobject gtk4 libadwaita libsecret
python3 nextcloud_notes.py
```

The Nextcloud Notes app API is enabled by default in current Notes releases.
The client tries API v1 first and falls back to v0.2 for older servers.

## Install locally

```bash
install -Dm755 nextcloud_notes.py ~/.local/lib/omarchy-app-nextcloud-notes/nextcloud_notes.py
sed "s#^Exec=.*#Exec=python3 $HOME/.local/lib/omarchy-app-nextcloud-notes/nextcloud_notes.py#" \
  nextcloud-notes.desktop > ~/.local/share/applications/nextcloud-notes.desktop
```

## Development

```bash
python3 -m py_compile nextcloud_notes.py
python3 -m unittest discover -v
```

## License

MIT
