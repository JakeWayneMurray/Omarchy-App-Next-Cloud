pkgname=omarchy-app-nextcloud-notes
pkgver=0.1.0.r13.gcbe9287
pkgrel=1
pkgdesc='Omarchy-styled Quickshell desktop client for Nextcloud Notes'
arch=('any')
url='https://github.com/JakeWayneMurray/Omarchy-App-Next-Cloud'
license=('MIT')
depends=('quickshell' 'python' 'libsecret')
makedepends=('git')
source=('git+https://github.com/JakeWayneMurray/Omarchy-App-Next-Cloud.git')
sha256sums=('SKIP')

pkgver() {
  cd "$srcdir/Omarchy-App-Next-Cloud"
  printf '0.1.0.r%s.g%s' "$(git rev-list --count HEAD)" "$(git rev-parse --short HEAD)"
}

package() {
  local appdir="$pkgdir/usr/share/$pkgname"
  local sourcedir="$srcdir/Omarchy-App-Next-Cloud"

  install -dm755 "$appdir"
  install -Dm644 "$sourcedir/App.qml" "$appdir/App.qml"
  install -Dm755 "$sourcedir/nextcloud_client.py" "$appdir/nextcloud_client.py"
  install -Dm755 "$sourcedir/run.sh" "$appdir/run.sh"
  install -Dm644 "$sourcedir/LICENSE" "$appdir/LICENSE"
  ln -s /usr/share/omarchy/shell/Commons "$appdir/Commons"
  ln -s /usr/share/omarchy/shell/Ui "$appdir/Ui"

  install -dm755 "$pkgdir/usr/share/applications"
  sed "s#^Exec=.*#Exec=/usr/share/$pkgname/run.sh#" \
    "$sourcedir/nextcloud-notes.desktop" > "$pkgdir/usr/share/applications/nextcloud-notes.desktop"
}
