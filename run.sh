#!/bin/sh
set -eu

app_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
import_path=/usr/share/omarchy/shell
ln -sfn /usr/share/omarchy/shell/Commons "$app_dir/Commons"
ln -sfn /usr/share/omarchy/shell/Ui "$app_dir/Ui"
if [ -n "${QML2_IMPORT_PATH:-}" ]; then
  import_path="$import_path:$QML2_IMPORT_PATH"
fi
export QML2_IMPORT_PATH="$import_path"
export QML_IMPORT_PATH="$import_path"
exec quickshell --path "$app_dir/App.qml" "$@"
