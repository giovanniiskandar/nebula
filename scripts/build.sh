#!/bin/sh
# Build Nebula.app and a disk image into release/.
#
# Everything lands in release/ rather than dist/, which belongs to Vite and is
# emptied on every frontend build.
set -e

ROOT=$(cd "$(dirname "$0")/.." && pwd)
cd "$ROOT"

VERSION=$(sed -n 's/^version = "\(.*\)"/\1/p' pyproject.toml | head -1)
echo "Building Nebula $VERSION"

# The frontend build is not optional: a stale or missing dist/ produces a
# bundle that fails at runtime rather than at build time.
echo "==> frontend"
export NVM_DIR="$HOME/.nvm"
if [ -s "$NVM_DIR/nvm.sh" ]; then
  . "$NVM_DIR/nvm.sh"
  nvm use --silent
fi
(cd frontend && pnpm install --frozen-lockfile && pnpm build)

echo "==> freezing"
rm -rf release/Nebula.app release/Nebula release/build
uv run pyinstaller nebula.spec --noconfirm \
  --distpath release --workpath release/build

echo "==> disk image"
STAGE=release/dmg
rm -rf "$STAGE" "release/Nebula-$VERSION.dmg"
mkdir -p "$STAGE"
cp -R release/Nebula.app "$STAGE/"
cp packaging/first-run.txt "$STAGE/Read Me First.txt"
ln -s /Applications "$STAGE/Applications"

hdiutil create -volname "Nebula $VERSION" -srcfolder "$STAGE" \
  -ov -format UDZO "release/Nebula-$VERSION.dmg" >/dev/null
rm -rf "$STAGE"

echo
echo "release/Nebula.app"
echo "release/Nebula-$VERSION.dmg  ($(du -h "release/Nebula-$VERSION.dmg" | cut -f1))"
