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

## Install on another Omarchy machine

The recommended install uses the repository's `PKGBUILD`; no AUR account is
required:

```bash
sudo pacman -S --needed base-devel git quickshell python libsecret
mkdir -p ~/Work
git clone git@github.com:JakeWayneMurray/Omarchy-App-Next-Cloud.git \
  ~/Work/Omarchy-App-Next-Cloud
cd ~/Work/Omarchy-App-Next-Cloud
makepkg -si
```

Launch **Nextcloud Notes** from the Omarchy application launcher. The app
stores its URL and username in `~/.config/omarchy/nextcloud-notes-app/` and
the password in the desktop keyring.

To update an existing installation:

```bash
cd ~/Work/Omarchy-App-Next-Cloud
git pull
makepkg -fsi
```

The Nextcloud Notes app API is enabled by default in current Notes releases.
The client tries API v1 first and falls back to v0.2 for older servers.

## Run from a checkout

For development or a quick local test, install the runtime dependencies and
run the app directly:

```bash
sudo pacman -S --needed quickshell python libsecret
./run.sh
```

## Development

```bash
python3 -m py_compile nextcloud_client.py
python3 -m unittest discover -v
```

## License

MIT
