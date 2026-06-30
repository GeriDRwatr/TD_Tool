#!/usr/bin/env bash
# =============================================================================
# TDTool — Linux packaging script
# Produces:
#   dist_linux/TDTool-1.0.0-x86_64.AppImage   (universal)
#   dist_linux/tdtool_1.0.0_amd64.deb          (Debian / Ubuntu / Mint)
#   dist_linux/tdtool-1.0.0-1.x86_64.rpm       (Fedora / RHEL / openSUSE)
#
# Usage (run from the project root):
#   bash linux/build.sh               # all formats
#   bash linux/build.sh --appimage    # AppImage only
#   bash linux/build.sh --deb         # .deb only
#   bash linux/build.sh --rpm         # .rpm only  (needs rpm-build)
#   bash linux/build.sh --deb --rpm   # combine flags freely
#
# Prerequisites (install once):
#   pip install pyinstaller pyinstaller-hooks-contrib PySide6 PyMuPDF
#   sudo apt install dpkg fuse libfuse2 curl        # Debian/Ubuntu
#   sudo dnf install rpm-build fuse fuse-libs curl  # Fedora/RHEL
#
# Optional — place a 256×256 PNG at linux/tdtool.png before running.
# A solid-colour placeholder is auto-generated if the file is absent.
# =============================================================================
set -euo pipefail

# ── Configuration ─────────────────────────────────────────────────────────────
APP_NAME="TDTool"
APP_ID="tdtool"
VERSION="1.0.0"
SUMMARY="PDF Viewer and Page Editor"
LONG_DESC="TDTool lets you view PDFs and rearrange, split or merge pages
 into separate documents by assigning them to named groups."
MAINTAINER="TDTool <noreply@example.com>"
HOMEPAGE="https://github.com/example/tdtool"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(dirname "$SCRIPT_DIR")"
PYINST_OUT="$ROOT/dist/$APP_NAME"
OUT="$ROOT/dist_linux"
ICON_SRC="$SCRIPT_DIR/tdtool.png"

ARCH_RAW="$(uname -m)"                       # x86_64 | aarch64 | armv7l
DEB_ARCH="${ARCH_RAW/x86_64/amd64}"
DEB_ARCH="${DEB_ARCH/aarch64/arm64}"
DEB_ARCH="${DEB_ARCH/armv7l/armhf}"

# ── Helpers ───────────────────────────────────────────────────────────────────
step() { printf '\n\033[1;36m══  %s  ══\033[0m\n' "$*"; }
ok()   { printf '  \033[0;32m✓\033[0m  %s\n'     "$*"; }
info() { printf '  \033[0;34m·\033[0m  %s\n'     "$*"; }
warn() { printf '  \033[0;33m!\033[0m  %s\n'     "$*"; }
die()  { printf '\033[1;31m✗  ERROR: %s\033[0m\n' "$*" >&2; exit 1; }

need() { command -v "$1" >/dev/null 2>&1; }

# ── Argument parsing ──────────────────────────────────────────────────────────
DO_APPIMAGE=false; DO_DEB=false; DO_RPM=false

if [[ $# -eq 0 ]]; then
    DO_APPIMAGE=true; DO_DEB=true; DO_RPM=true
else
    for arg in "$@"; do
        case "$arg" in
            --appimage) DO_APPIMAGE=true ;;
            --deb)      DO_DEB=true      ;;
            --rpm)      DO_RPM=true      ;;
            --all)      DO_APPIMAGE=true; DO_DEB=true; DO_RPM=true ;;
            *) die "Unknown option: $arg.  Use --appimage | --deb | --rpm | --all" ;;
        esac
    done
fi

mkdir -p "$OUT"

# ── 1. Prerequisites ──────────────────────────────────────────────────────────
step "Checking prerequisites"

need python3 || die "python3 not found"
python3 -c "import PyInstaller" 2>/dev/null \
    || die "PyInstaller missing — run: pip install pyinstaller pyinstaller-hooks-contrib"
python3 -c "import PySide6"    2>/dev/null || die "PySide6 missing — run: pip install PySide6"
python3 -c "import fitz"       2>/dev/null || die "PyMuPDF missing — run: pip install PyMuPDF"

$DO_DEB && { need dpkg-deb || die "dpkg-deb not found — run: sudo apt install dpkg"; }
$DO_RPM && { need rpmbuild  || die "rpmbuild not found — run: sudo dnf install rpm-build  OR  sudo apt install rpm"; }

ok "Tools OK"

# ── 2. PyInstaller ────────────────────────────────────────────────────────────
step "Building with PyInstaller"
cd "$ROOT"
python3 -m PyInstaller linux/TDTool_linux.spec --noconfirm
[[ -d "$PYINST_OUT" ]] || die "PyInstaller output not found at $PYINST_OUT"
ok "PyInstaller → $PYINST_OUT"

# ── 3. Icon ───────────────────────────────────────────────────────────────────
if [[ ! -f "$ICON_SRC" ]]; then
    warn "linux/tdtool.png not found — generating placeholder"
    python3 <<PYEOF
import struct, zlib, os

def make_png(w, h, r, g, b):
    """Minimal solid-colour PNG using only stdlib (no PIL required)."""
    def chunk(tag, data):
        raw = tag + data
        return struct.pack('>I', len(data)) + raw + struct.pack('>I', zlib.crc32(raw) & 0xffffffff)
    ihdr = struct.pack('>IIBBBBB', w, h, 8, 2, 0, 0, 0)   # 8-bit RGB, no interlace
    rows = b''.join(b'\\x00' + bytes([r, g, b] * w) for _ in range(h))
    return (b'\\x89PNG\\r\\n\\x1a\\n'
            + chunk(b'IHDR', ihdr)
            + chunk(b'IDAT', zlib.compress(rows, 9))
            + chunk(b'IEND', b''))

with open('${ICON_SRC}', 'wb') as f:
    f.write(make_png(256, 256, 30, 50, 120))
print("  placeholder icon written")
PYEOF
fi
ok "Icon: $ICON_SRC"

# ── 4. AppImage ───────────────────────────────────────────────────────────────
if $DO_APPIMAGE; then
    step "Building AppImage"

    APPDIR="$OUT/AppDir"
    rm -rf "$APPDIR"
    mkdir -p \
        "$APPDIR/usr/bin" \
        "$APPDIR/usr/share/applications" \
        "$APPDIR/usr/share/icons/hicolor/256x256/apps"

    # Copy entire PyInstaller onedir output into AppDir/usr/bin/
    cp -r "$PYINST_OUT/." "$APPDIR/usr/bin/"

    # Desktop entry — AppImage spec requires it both at root AND in usr/share
    cp "$SCRIPT_DIR/tdtool.desktop" "$APPDIR/"
    cp "$SCRIPT_DIR/tdtool.desktop" "$APPDIR/usr/share/applications/"

    # Icon — same requirement (root + hicolor)
    cp "$ICON_SRC" "$APPDIR/tdtool.png"
    cp "$ICON_SRC" "$APPDIR/usr/share/icons/hicolor/256x256/apps/tdtool.png"

    # AppRun entry point
    cp "$SCRIPT_DIR/AppRun" "$APPDIR/AppRun"
    chmod +x "$APPDIR/AppRun"

    # Download appimagetool if not cached
    APPIMAGETOOL="$OUT/appimagetool-${ARCH_RAW}.AppImage"
    if [[ ! -x "$APPIMAGETOOL" ]]; then
        info "Downloading appimagetool (one-time)..."
        TOOL_URL="https://github.com/AppImage/AppImageKit/releases/download/continuous/appimagetool-${ARCH_RAW}.AppImage"
        curl -fsSL "$TOOL_URL" -o "$APPIMAGETOOL"
        chmod +x "$APPIMAGETOOL"
    fi

    APPIMAGE_FILE="$OUT/${APP_NAME}-${VERSION}-${ARCH_RAW}.AppImage"
    ARCH="$ARCH_RAW" "$APPIMAGETOOL" --no-appstream "$APPDIR" "$APPIMAGE_FILE"
    ok "AppImage → $APPIMAGE_FILE"
fi

# ── 5. .deb ───────────────────────────────────────────────────────────────────
if $DO_DEB; then
    step "Building .deb package"

    DEB_PKG="$OUT/deb_build/${APP_ID}_${VERSION}_${DEB_ARCH}"
    LIB_DIR="$DEB_PKG/usr/lib/$APP_ID"

    rm -rf "$DEB_PKG"
    mkdir -p \
        "$DEB_PKG/DEBIAN" \
        "$LIB_DIR" \
        "$DEB_PKG/usr/bin" \
        "$DEB_PKG/usr/share/applications" \
        "$DEB_PKG/usr/share/icons/hicolor/256x256/apps" \
        "$DEB_PKG/usr/share/mime/packages"

    # App files
    cp -r "$PYINST_OUT/." "$LIB_DIR/"

    # Thin launcher in /usr/bin so users can type `tdtool` in a terminal
    cat > "$DEB_PKG/usr/bin/$APP_ID" <<SH
#!/bin/sh
exec /usr/lib/${APP_ID}/${APP_NAME} "\$@"
SH
    chmod +x "$DEB_PKG/usr/bin/$APP_ID"

    # Desktop entry + icon
    cp "$SCRIPT_DIR/tdtool.desktop" "$DEB_PKG/usr/share/applications/"
    cp "$ICON_SRC"                        "$DEB_PKG/usr/share/icons/hicolor/256x256/apps/tdtool.png"

    # MIME type declaration (registers PDF association for XDG)
    cat > "$DEB_PKG/usr/share/mime/packages/${APP_ID}.xml" <<XML
<?xml version="1.0" encoding="UTF-8"?>
<mime-info xmlns="http://www.freedesktop.org/standards/shared-mime-info">
  <mime-type type="application/pdf">
    <comment>PDF Document</comment>
    <glob pattern="*.pdf"/>
  </mime-type>
</mime-info>
XML

    # DEBIAN/control
    INSTALLED_KB=$(du -sk "$LIB_DIR" | awk '{print $1}')
    cat > "$DEB_PKG/DEBIAN/control" <<CTRL
Package: ${APP_ID}
Version: ${VERSION}
Architecture: ${DEB_ARCH}
Maintainer: ${MAINTAINER}
Installed-Size: ${INSTALLED_KB}
Depends: libgl1, libglib2.0-0, libdbus-1-3, libxcb1, libxkbcommon0
Recommends: libfuse2
Section: graphics
Priority: optional
Homepage: ${HOMEPAGE}
Description: ${SUMMARY}
 ${LONG_DESC}
CTRL

    # DEBIAN/postinst — refresh desktop/MIME databases after install
    cat > "$DEB_PKG/DEBIAN/postinst" <<'SH'
#!/bin/sh
set -e
command -v update-desktop-database >/dev/null && update-desktop-database /usr/share/applications || true
command -v update-mime-database    >/dev/null && update-mime-database    /usr/share/mime         || true
command -v gtk-update-icon-cache   >/dev/null && gtk-update-icon-cache -f -t /usr/share/icons/hicolor 2>/dev/null || true
SH

    # DEBIAN/postrm — clean up databases on uninstall
    cat > "$DEB_PKG/DEBIAN/postrm" <<'SH'
#!/bin/sh
set -e
command -v update-desktop-database >/dev/null && update-desktop-database /usr/share/applications || true
command -v update-mime-database    >/dev/null && update-mime-database    /usr/share/mime         || true
SH

    chmod 755 "$DEB_PKG/DEBIAN/postinst" "$DEB_PKG/DEBIAN/postrm"

    DEB_FILE="$OUT/${APP_ID}_${VERSION}_${DEB_ARCH}.deb"
    dpkg-deb --build --root-owner-group "$DEB_PKG" "$DEB_FILE"
    ok ".deb → $DEB_FILE"
    info "Install:   sudo dpkg -i $DEB_FILE"
    info "Uninstall: sudo apt remove $APP_ID"
fi

# ── 6. .rpm ───────────────────────────────────────────────────────────────────
if $DO_RPM; then
    step "Building RPM package"

    RPM_ROOT="$OUT/rpm_build"
    rm -rf "$RPM_ROOT"
    mkdir -p "$RPM_ROOT"/{BUILD,RPMS,SOURCES,SPECS,SRPMS}

    # Create source tarball from PyInstaller output
    TARBALL="$RPM_ROOT/SOURCES/${APP_ID}-${VERSION}.tar.gz"
    tar -czf "$TARBALL" -C "$(dirname "$PYINST_OUT")" "$APP_NAME"
    info "Source tarball: $TARBALL"

    # Also stage desktop + icon + MIME file alongside the tarball
    cp "$SCRIPT_DIR/tdtool.desktop" "$RPM_ROOT/SOURCES/"
    cp "$ICON_SRC"                        "$RPM_ROOT/SOURCES/tdtool.png"

    cat > "$RPM_ROOT/SOURCES/tdtool-mime.xml" <<XML
<?xml version="1.0" encoding="UTF-8"?>
<mime-info xmlns="http://www.freedesktop.org/standards/shared-mime-info">
  <mime-type type="application/pdf">
    <comment>PDF Document</comment>
    <glob pattern="*.pdf"/>
  </mime-type>
</mime-info>
XML

    # Generate the RPM .spec inside rpmbuild's SPECS tree
    cat > "$RPM_ROOT/SPECS/${APP_ID}.spec" <<RPMSPEC
Name:           ${APP_ID}
Version:        ${VERSION}
Release:        1%{?dist}
Summary:        ${SUMMARY}
License:        Proprietary
URL:            ${HOMEPAGE}
Source0:        ${APP_ID}-${VERSION}.tar.gz
Source1:        tdtool.desktop
Source2:        tdtool.png
Source3:        tdtool-mime.xml

Requires:       libGL, glib2, dbus-libs, libxcb, libxkbcommon

%description
${LONG_DESC}

%prep
# Nothing to compile — pre-built PyInstaller bundle

%install
rm -rf %{buildroot}

install -d %{buildroot}/usr/lib/${APP_ID}
install -d %{buildroot}/usr/bin
install -d %{buildroot}/usr/share/applications
install -d %{buildroot}/usr/share/icons/hicolor/256x256/apps
install -d %{buildroot}/usr/share/mime/packages

# App files from tarball (extracted in SOURCES)
cp -r %{_sourcedir}/${APP_NAME}/. %{buildroot}/usr/lib/${APP_ID}/

# Thin launcher
cat > %{buildroot}/usr/bin/${APP_ID} <<'LAUNCHER'
#!/bin/sh
exec /usr/lib/${APP_ID}/${APP_NAME} "\$@"
LAUNCHER
chmod 755 %{buildroot}/usr/bin/${APP_ID}

install -m 644 %{SOURCE1} %{buildroot}/usr/share/applications/
install -m 644 %{SOURCE2} %{buildroot}/usr/share/icons/hicolor/256x256/apps/tdtool.png
install -m 644 %{SOURCE3} %{buildroot}/usr/share/mime/packages/tdtool.xml

%post
update-desktop-database /usr/share/applications &>/dev/null || true
update-mime-database    /usr/share/mime         &>/dev/null || true
gtk-update-icon-cache -f -t /usr/share/icons/hicolor &>/dev/null || true

%postun
update-desktop-database /usr/share/applications &>/dev/null || true
update-mime-database    /usr/share/mime         &>/dev/null || true

%files
/usr/lib/${APP_ID}/
/usr/bin/${APP_ID}
/usr/share/applications/tdtool.desktop
/usr/share/icons/hicolor/256x256/apps/tdtool.png
/usr/share/mime/packages/tdtool.xml

%changelog
* $(date '+%a %b %d %Y') Build System <noreply@example.com> - ${VERSION}-1
- Initial package
RPMSPEC

    # Extract tarball into BUILD so RPM spec's cp can find the files
    tar -xzf "$TARBALL" -C "$RPM_ROOT/SOURCES"

    rpmbuild \
        --define "_topdir $RPM_ROOT" \
        --define "_builddir $RPM_ROOT/BUILD" \
        -bb "$RPM_ROOT/SPECS/${APP_ID}.spec"

    RPM_FILE=$(find "$RPM_ROOT/RPMS" -name "*.rpm" | head -n1)
    cp "$RPM_FILE" "$OUT/"
    ok ".rpm → $OUT/$(basename "$RPM_FILE")"
    info "Install:   sudo rpm -i $(basename "$RPM_FILE")"
    info "Uninstall: sudo rpm -e $APP_ID"
fi

# ── Done ──────────────────────────────────────────────────────────────────────
step "Done"
echo
printf '  Output directory: %s\n' "$OUT"
ls -lh "$OUT"/*.AppImage "$OUT"/*.deb "$OUT"/*.rpm 2>/dev/null || true
echo
