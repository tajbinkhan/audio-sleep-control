#!/bin/sh
# Build audio-sleep-control_<version>_all.deb into dist/.
# Usage: packaging/deb/build-deb.sh [version]   (default: version from the source)
set -eu

cd "$(dirname "$0")/../.."
ID=io.github.tajbinkhan.AudioSleepControl
VERSION="${1:-$(sed -n 's/^__version__ = "\(.*\)"/\1/p' src/audio_sleep_control.py)}"
VERSION="${VERSION#v}"
PKG=audio-sleep-control
ROOT="build/${PKG}_${VERSION}_all"

rm -rf "$ROOT"
mkdir -p "$ROOT/DEBIAN" "$ROOT/usr/bin" "$ROOT/usr/share/applications" \
  "$ROOT/usr/share/metainfo" "$ROOT/usr/share/icons/hicolor/scalable/apps" \
  "$ROOT/usr/share/doc/$PKG" dist

sed "s/^__version__ = .*/__version__ = \"$VERSION\"/" src/audio_sleep_control.py > "$ROOT/usr/bin/$PKG"
cp "data/$ID.desktop" "$ROOT/usr/share/applications/"
cp "data/$ID.metainfo.xml" "$ROOT/usr/share/metainfo/"
cp "data/icons/hicolor/scalable/apps/$ID.svg" "$ROOT/usr/share/icons/hicolor/scalable/apps/"

{
  echo "Format: https://www.debian.org/doc/packaging-manuals/copyright-format/1.0/"
  echo "Upstream-Name: $PKG"
  echo "Source: https://github.com/tajbinkhan/audio-sleep-control"
  echo
  echo "Files: *"
  echo "Copyright: 2026 Tajbin Khan"
  echo "License: MIT"
  sed -n '3,$p' LICENSE | sed 's/^$/./; s/^/ /'
} > "$ROOT/usr/share/doc/$PKG/copyright"

cat > "$ROOT/DEBIAN/control" <<EOF
Package: $PKG
Version: $VERSION
Section: sound
Priority: optional
Architecture: all
Depends: python3, python3-gi, gir1.2-gtk-4.0, gir1.2-adw-1 (>= 1.5), pipewire-bin, wireplumber (>= 0.5), pkexec | policykit-1
Maintainer: Tajbin Khan <61348041+tajbinkhan@users.noreply.github.com>
Homepage: https://github.com/tajbinkhan/audio-sleep-control
Description: Keep your speaker output from going to sleep
 A small GNOME app that shows whether your sound output is playing,
 idle or asleep, and lets you stop PipeWire/WirePlumber from suspending
 it and turn off the HDA sound chip's power saving.
Installed-Size: $(du -sk "$ROOT/usr" | cut -f1)
EOF

for s in postinst postrm; do
  cat > "$ROOT/DEBIAN/$s" <<'EOF'
#!/bin/sh
set -e
command -v update-desktop-database >/dev/null && update-desktop-database -q /usr/share/applications || true
command -v gtk-update-icon-cache >/dev/null && gtk-update-icon-cache -q -t /usr/share/icons/hicolor || true
EOF
done

find "$ROOT" -type d -exec chmod 755 {} +
find "$ROOT/usr" -type f -exec chmod 644 {} +
chmod 644 "$ROOT/DEBIAN/control"
chmod 755 "$ROOT/usr/bin/$PKG" "$ROOT/DEBIAN/postinst" "$ROOT/DEBIAN/postrm"

dpkg-deb --root-owner-group --build "$ROOT" "dist/${PKG}_${VERSION}_all.deb"
