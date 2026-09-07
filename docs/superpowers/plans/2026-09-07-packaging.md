# Packaging and Distribution Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Produce a `Nebula.app` inside a `.dmg` that a friend can install and run.

**Architecture:** A committed `nebula.spec` freezes the app with PyInstaller, carrying the `Info.plist` values — including the reverse-DNS bundle identifier that makes macOS single-instance it. `scripts/build.sh` runs the frontend build, the freeze and `hdiutil` in order, into `release/`. A slow test builds the real artifact and launches it.

**Tech Stack:** PyInstaller, `hdiutil`, Python 3.13, pywebview, pnpm, pytest.

**Spec:** `docs/superpowers/specs/2026-09-07-packaging-design.md`

## Global Constraints

- Node `>=24 <25`. Every frontend command must be preceded by
  `export NVM_DIR="$HOME/.nvm" && . "$NVM_DIR/nvm.sh" && nvm use`.
- **Output goes to `release/`, never `dist/`.** PyInstaller defaults to `dist/`,
  which is Vite's output and is emptied by every `pnpm build`.
- `CFBundleIdentifier` is exactly `com.giovanniiskandar.nebula`. A bare name
  does not single-instance (spec §3), so this value is load-bearing.
- `CFBundleShortVersionString` is read from `pyproject.toml`, never repeated.
- **`--add-data` resolves relative to `--specpath`, not the working directory.**
  Use absolute paths (spike finding).
- The bundle is arm64 only and ad-hoc signed. Signing, notarisation and
  universal2 are out of scope (PRD §24).
- The bundle test is marked `slow`; the hook's selector becomes
  `-m "not gui and not slow"`.
- No `js_api` method may destroy the window (phase 2 deadlock).

---

## File Structure

| File | Responsibility |
|---|---|
| `src/nebula/app.py` | `PROJECT_ROOT` resolving through `sys._MEIPASS` |
| `nebula.spec` | The freeze: data files, and every `Info.plist` value |
| `scripts/build.sh` | frontend build → freeze → disk image, into `release/` |
| `packaging/first-run.txt` | What the recipient reads before launching |
| `tests/test_bundle.py` | Builds the real artifact and launches it |
| `.gitignore` | `release/` |
| `pyproject.toml` | PyInstaller dev dependency; the `slow` marker |

---

### Task 1: Find the frontend inside a bundle

**Files:**
- Modify: `src/nebula/app.py`, `pyproject.toml`, `.gitignore`
- Test: `tests/test_bundle_paths.py`

**Interfaces:**
- Consumes: nothing.
- Produces: `app.PROJECT_ROOT` correct in both modes; `app.resolve_project_root() -> Path`.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_bundle_paths.py`:

```python
"""Where the app looks for its frontend and icon, frozen or not."""

import sys
from pathlib import Path

from nebula import app


def test_from_a_source_checkout_the_root_is_the_repo():
    """src/nebula/app.py -> the repo containing pyproject.toml."""
    root = app.resolve_project_root()
    assert (root / "pyproject.toml").exists()


def test_inside_a_bundle_the_root_is_meipass(monkeypatch):
    """PyInstaller unpacks data next to the executable, not beside the source."""
    monkeypatch.setattr(sys, "_MEIPASS", "/tmp/nebula-bundle", raising=False)
    assert app.resolve_project_root() == Path("/tmp/nebula-bundle")


def test_the_frontend_and_icon_hang_off_the_root(monkeypatch):
    monkeypatch.setattr(sys, "_MEIPASS", "/tmp/nebula-bundle", raising=False)
    root = app.resolve_project_root()
    assert root / "dist" / "index.html" == Path("/tmp/nebula-bundle/dist/index.html")
    assert root / "assets" / "Nebula.icns" == Path(
        "/tmp/nebula-bundle/assets/Nebula.icns"
    )
```

- [ ] **Step 2: Run them to verify they fail**

```bash
cd /Users/macbook/Documents/Projects/nebula
uv run pytest tests/test_bundle_paths.py -v
```

Expected: FAIL — `AttributeError: module 'nebula.app' has no attribute 'resolve_project_root'`.

- [ ] **Step 3: Implement it**

In `src/nebula/app.py`, replace the `PROJECT_ROOT` block:

```python
def resolve_project_root() -> Path:
    """Where `dist/` and `assets/` live.

    PyInstaller unpacks bundled data into a temporary directory and points
    `sys._MEIPASS` at it, so the frozen app must look there rather than beside
    its own source. From a source checkout the answer is the repo root:
    src/nebula/app.py -> nebula/.
    """
    bundled = getattr(sys, "_MEIPASS", None)
    if bundled is not None:
        return Path(bundled)
    return Path(__file__).resolve().parents[2]


PROJECT_ROOT = resolve_project_root()
DIST_INDEX = PROJECT_ROOT / "dist" / "index.html"
ICON_PATH = PROJECT_ROOT / "assets" / "Nebula.icns"
```

`store.data_path` is untouched: it already uses `Path.home()`, which a bundled
app needs because its working directory is `/`.

- [ ] **Step 4: Run them to verify they pass**

```bash
uv run pytest tests/test_bundle_paths.py -v
```

Expected: 3 passed.

- [ ] **Step 5: Add PyInstaller and the slow marker**

In `pyproject.toml`, add to `[dependency-groups] dev`:

```toml
    "pyinstaller>=6.22",
```

and to `[tool.pytest.ini_options] markers`:

```toml
    "slow: builds a real .app; skipped by the pre-commit hook",
```

Then sync:

```bash
uv sync
```

- [ ] **Step 6: Ignore the build output**

In `.gitignore`, under the `# Frontend` block's `dist/` line, add:

```
# Packaged app and disk image
release/
```

- [ ] **Step 7: Update the hook's selector**

In `.githooks/pre-commit`, change the pytest line:

```sh
uv run pytest -q -m "not gui and not slow"
```

- [ ] **Step 8: Run the whole suite**

```bash
uv run pytest -q
```

Expected: all pass.

- [ ] **Step 9: Commit**

```bash
git add -A
git commit -m "Find the frontend inside a bundle

PyInstaller unpacks bundled data into a temporary directory and points
sys._MEIPASS at it, so a frozen app cannot look beside its own source.
Without this the app exits with 'Frontend not built' -- loudly and with
the wrong advice, since the frontend is built and merely elsewhere.

store.data_path is untouched: it already uses Path.home(), which a
bundled app needs because its working directory is /."
```

---

### Task 2: The freeze

**Files:**
- Create: `nebula.spec`
- Test: `tests/test_bundle.py` (the plist assertions)

**Interfaces:**
- Consumes: `resolve_project_root` from Task 1.
- Produces: `release/Nebula.app` when built with
  `uv run pyinstaller nebula.spec --distpath release --workpath release/build`.

- [ ] **Step 1: Generate a baseline spec from the invocation the spike verified**

Hand-writing a PyInstaller spec means guessing at its API, and a wrong guess
fails obscurely. Generate one from the CLI flags the spike proved work, then
patch it — the generated file is guaranteed to match the installed version.

```bash
cd /Users/macbook/Documents/Projects/nebula
export NVM_DIR="$HOME/.nvm" && . "$NVM_DIR/nvm.sh" && nvm use
(cd frontend && pnpm build)

R=$(pwd)
uv run pyinstaller \
  --name Nebula --windowed --noconfirm \
  --osx-bundle-identifier com.giovanniiskandar.nebula \
  --paths "$R/src" \
  --add-data "$R/dist:dist" \
  --add-data "$R/assets/Nebula.icns:assets" \
  --icon "$R/assets/Nebula.icns" \
  --distpath release --workpath release/build --specpath . \
  src/nebula/__main__.py
```

This writes `Nebula.spec` at the repo root and builds once. Rename it:

```bash
mv Nebula.spec nebula.spec
```

- [ ] **Step 2: Patch the spec to read the version and set the plist**

The generated spec hardcodes absolute paths from this machine and carries no
version. Apply these three edits to `nebula.spec`.

At the top, after the existing imports (or as the first lines if there are
none):

```python
# Build with:
#   uv run pyinstaller nebula.spec --distpath release --workpath release/build
#
# `dist/` is Vite's output and is emptied by every `pnpm build`, so the app is
# written to `release/` instead -- the two must not share a directory.
import tomllib
from pathlib import Path

ROOT = Path(SPECPATH)

with (ROOT / "pyproject.toml").open("rb") as handle:
    VERSION = tomllib.load(handle)["project"]["version"]
```

Replace every absolute path the generator baked in (they will read
`/Users/macbook/Documents/Projects/nebula/...`) with `ROOT`-relative ones, so
the spec works from any checkout:

```python
    [str(ROOT / "src" / "nebula" / "__main__.py")],
    pathex=[str(ROOT / "src")],
    datas=[
        (str(ROOT / "dist"), "dist"),
        (str(ROOT / "assets" / "Nebula.icns"), "assets"),
    ],
```

and in both `EXE(...)` and `BUNDLE(...)`, `icon=str(ROOT / "assets" / "Nebula.icns")`.

Then extend the `BUNDLE(...)` call:

```python
app = BUNDLE(
    coll,
    name="Nebula.app",
    icon=str(ROOT / "assets" / "Nebula.icns"),
    # Reverse-DNS is load-bearing, not cosmetic: with a bare name macOS starts
    # a second process per launch. With this, LaunchServices single-instances
    # the app, which is what closes PRD §15.
    bundle_identifier="com.giovanniiskandar.nebula",
    version=VERSION,
    info_plist={
        "CFBundleName": "Nebula",
        "CFBundleDisplayName": "Nebula",
        "CFBundleShortVersionString": VERSION,
        "CFBundleVersion": VERSION,
        "CFBundleIconFile": "Nebula.icns",
        "NSHighResolutionCapable": True,
    },
)
```

Keep the generator's own variable names — it may call the `COLLECT` result
`coll` rather than `collect`; use whatever is there rather than renaming.

- [ ] **Step 3: Rebuild from the patched spec**

```bash
cd /Users/macbook/Documents/Projects/nebula
rm -rf release
uv run pyinstaller nebula.spec --noconfirm --distpath release --workpath release/build
```

Expected: `release/Nebula.app` exists. Building from the spec rather than the
CLI flags is what the build script will do.

- [ ] **Step 4: Check the plist by hand**

```bash
APP=release/Nebula.app
for key in CFBundleIdentifier CFBundleShortVersionString CFBundleName CFBundleIconFile; do
  printf "%-28s %s\n" "$key" "$(/usr/libexec/PlistBuddy -c "Print :$key" "$APP/Contents/Info.plist")"
done
```

Expected: `com.giovanniiskandar.nebula`, `0.1.0`, `Nebula`, `Nebula.icns`.

- [ ] **Step 5: Launch it from Finder**

```bash
open release/Nebula.app
sleep 5
pgrep -f "Nebula.app/Contents/MacOS" | wc -l
```

Expected: `1`, and the card appears with your real allocations. If it shows
"Frontend not built", Task 1 did not take effect.

- [ ] **Step 6: Confirm the single-instance behaviour**

```bash
open release/Nebula.app
sleep 4
pgrep -f "Nebula.app/Contents/MacOS" | wc -l
```

Expected: still `1`. Then close the window with the `×`.

- [ ] **Step 7: Commit**

```bash
git add -A
git commit -m "Freeze the app with a committed PyInstaller spec

The spec reads the version from pyproject.toml rather than repeating it,
which is what the spike found drifting: the plist said 0.0.0 while the
project said 0.1.0.

CFBundleIdentifier is reverse-DNS because that is load-bearing rather
than cosmetic. With PyInstaller's default bare name, macOS starts a
second process on every launch; with this, LaunchServices
single-instances the app, closing PRD §15 with no code.

Data paths are absolute: --add-data resolves relative to the spec's own
directory, which cost the spike a failed build."
```

---

### Task 3: The build script and the disk image

**Files:**
- Create: `scripts/build.sh`, `packaging/first-run.txt`
- Modify: `README.md`

**Interfaces:**
- Consumes: `nebula.spec` from Task 2.
- Produces: `release/Nebula.app` and `release/Nebula-<version>.dmg`.

- [ ] **Step 1: Write the instructions the recipient reads**

Create `packaging/first-run.txt`:

```
Nebula — first run
==================

Nebula is not signed with an Apple Developer certificate, so macOS will
refuse to open it the first time. This is expected. Two ways past it:

  1. Right-click (or Control-click) Nebula in Applications and choose Open,
     then confirm. macOS remembers the choice.

  2. Or, in Terminal:

         xattr -cr /Applications/Nebula.app

     After that it opens normally, with no warnings.

Notifications
-------------

Nebula tells you when an allocation reaches 95% and 100% of its daily
target. It delivers those through macOS's built-in scripting, so the
banners are attributed to "Script Editor" rather than to Nebula.

That means their visibility is controlled by Script Editor's settings:

    System Settings > Notifications > Script Editor

If notifications for Script Editor are turned off, Nebula's notifications
will not appear and nothing will tell you why. If you want them, make sure
that is switched on and set to Banners or Alerts.

Your data
---------

Everything stays on this Mac, in:

    ~/Library/Application Support/Nebula/data.json

There is no account, no sync, and nothing is sent anywhere.
```

- [ ] **Step 2: Write the build script**

Create `scripts/build.sh`:

```sh
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
```

Make it executable:

```bash
chmod +x scripts/build.sh
```

- [ ] **Step 3: Run it**

```bash
cd /Users/macbook/Documents/Projects/nebula
./scripts/build.sh
```

Expected: both paths printed, and the `.dmg` around 28MB.

- [ ] **Step 4: Mount the disk image and look at it**

```bash
VERSION=$(sed -n 's/^version = "\(.*\)"/\1/p' pyproject.toml | head -1)
hdiutil attach "release/Nebula-$VERSION.dmg"
ls -la "/Volumes/Nebula $VERSION"
hdiutil detach "/Volumes/Nebula $VERSION"
```

Expected: `Nebula.app`, `Applications` (a symlink), and `Read Me First.txt`.

- [ ] **Step 5: Document it in the README**

Add a `## Building a release` section after `## Develop`:

```markdown
## Building a release

```sh
./scripts/build.sh
```

Produces `release/Nebula.app` and `release/Nebula-<version>.dmg`. The version
comes from `pyproject.toml` and is written into the app's `Info.plist`, so the
two cannot drift.

The app is unsigned, so the first launch needs the Gatekeeper override
described in `packaging/first-run.txt`, which ships inside the disk image.
```

- [ ] **Step 6: Commit**

```bash
git add -A
git commit -m "Add the release build and its first-run instructions

scripts/build.sh runs the frontend build, the freeze and hdiutil in
order, into release/. The frontend build is not optional: a stale dist/
produces a bundle that fails at runtime rather than at build time.

The disk image carries the app, a symlink to /Applications so dragging
across needs no explanation, and the instructions.

Those instructions cover the two things that fail silently. Gatekeeper
refuses an unsigned app on first launch, and notification visibility is
governed by Script Editor's settings rather than anything Nebula
controls -- with them off, no banner appears and nothing says why."
```

---

### Task 4: Testing the real artifact

**Files:**
- Create: `tests/test_bundle.py`
- Modify: `docs/ROADMAP.md`, `PRD.md`

**Interfaces:**
- Consumes: everything above.
- Produces: the finished phase.

- [ ] **Step 1: Write the test**

Create `tests/test_bundle.py`:

```python
"""The built .app, exercised as an artifact rather than as a recipe.

Every packaging bug found so far appeared only in a real bundle: a path that
resolves differently, a data file that was never collected, a plist value that
silently defaults. Asserting on the spec file would catch none of them.

Marked `slow` -- the build takes about a minute, so this stays out of the
pre-commit hook and runs on demand.
"""

import plistlib
import subprocess
import time
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
APP = PROJECT_ROOT / "release" / "Nebula.app"


def _running() -> int:
    result = subprocess.run(
        ["pgrep", "-f", "Nebula.app/Contents/MacOS"],
        capture_output=True,
        text=True,
        check=False,
    )
    return len([line for line in result.stdout.splitlines() if line.strip()])


def _quit() -> None:
    subprocess.run(
        ["pkill", "-f", "Nebula.app/Contents/MacOS"], check=False, capture_output=True
    )
    time.sleep(1)


@pytest.fixture(scope="module")
def built_app() -> Path:
    """Build once for the whole module; the build is the slow part."""
    subprocess.run(
        [str(PROJECT_ROOT / "scripts" / "build.sh")],
        cwd=PROJECT_ROOT,
        check=True,
        capture_output=True,
        text=True,
        timeout=600,
    )
    assert APP.exists()
    return APP


@pytest.mark.slow
def test_the_plist_carries_the_identity_macos_needs(built_app: Path):
    plist = plistlib.loads((built_app / "Contents" / "Info.plist").read_bytes())

    # Reverse-DNS is what makes macOS single-instance the app (spec §3).
    assert plist["CFBundleIdentifier"] == "com.giovanniiskandar.nebula"
    assert plist["CFBundleName"] == "Nebula"
    assert plist["CFBundleIconFile"] == "Nebula.icns"

    # The version is read from pyproject rather than repeated, so they agree.
    pyproject = (PROJECT_ROOT / "pyproject.toml").read_text()
    version = next(
        line.split('"')[1] for line in pyproject.splitlines()
        if line.startswith("version = ")
    )
    assert plist["CFBundleShortVersionString"] == version


@pytest.mark.slow
def test_the_frontend_is_inside_the_bundle(built_app: Path):
    """A missing data file only shows up at runtime, so check it is collected."""
    assert (built_app / "Contents" / "Frameworks" / "dist" / "index.html").exists()
    assert (built_app / "Contents" / "Frameworks" / "assets" / "Nebula.icns").exists()
    # pywebview globs these at runtime; static analysis cannot see them.
    js = list((built_app / "Contents" / "Resources" / "webview" / "js").glob("*.js"))
    assert len(js) >= 4, [p.name for p in js]


@pytest.mark.slow
def test_it_launches_and_shows_its_window(built_app: Path):
    _quit()
    try:
        subprocess.run(["open", str(built_app)], check=True)
        time.sleep(6)

        import Quartz

        windows = Quartz.CGWindowListCopyWindowInfo(
            Quartz.kCGWindowListOptionOnScreenOnly
            | Quartz.kCGWindowListExcludeDesktopElements,
            Quartz.kCGNullWindowID,
        )
        found = [
            dict(w["kCGWindowBounds"])
            for w in windows
            if str(w.get("kCGWindowOwnerName", "")) == "Nebula"
        ]
        assert found, "no window owned by Nebula"
        assert int(found[0]["Width"]) == 384
        assert int(found[0]["Height"]) == 684
    finally:
        _quit()


@pytest.mark.slow
def test_a_second_open_does_not_start_a_second_process(built_app: Path):
    """PRD §15, satisfied by the bundle identifier rather than by a lock."""
    _quit()
    try:
        subprocess.run(["open", str(built_app)], check=True)
        time.sleep(6)
        assert _running() == 1

        subprocess.run(["open", str(built_app)], check=True)
        time.sleep(4)
        assert _running() == 1
    finally:
        _quit()
```

- [ ] **Step 2: Run it**

```bash
cd /Users/macbook/Documents/Projects/nebula
uv run pytest tests/test_bundle.py -v -m slow
```

Expected: 4 passed, in roughly 90 seconds. **A window will appear and disappear
twice** during the run.

- [ ] **Step 3: Confirm the hook still skips it**

```bash
uv run pytest -q -m "not gui and not slow"
```

Expected: the usual fast suite, with the bundle tests deselected.

- [ ] **Step 4: Run everything**

```bash
uv run pytest -q
cd frontend && pnpm test && pnpm lint && cd ..
```

Expected: all pass.

- [ ] **Step 5: Tick the PRD's Distribution checklist**

In `PRD.md`, under **Distribution**, change both lines to `- [x]`:

```
- [x] Unsigned `.app` build
- [x] Bundled first-run instructions for the Gatekeeper override (§26)
```

And under **Time Tracking**, tick the single-instance line:

```
- [x] Handle application restart (single-instance guarded)
```

- [ ] **Step 6: Update the roadmap**

In `docs/ROADMAP.md`, move phase 4 to `**Done**` in the status table, remove the
`Next` marker from the table entirely since nothing follows, and rewrite the
"Phase 4 — Packaging and distribution" section in the style of the finished
phases. In **Verification gaps**, keep the "never run on another Mac" entry —
this phase does not close it — and note that the Gatekeeper prompt is still
untriggered.

- [ ] **Step 7: Commit**

```bash
git add -A
git commit -m "Test the built app as an artifact

Builds the real bundle and launches it: the plist identity, the frontend
and pywebview's runtime-globbed JS actually being inside, the window
appearing at 384x684, and a second open leaving one process.

That last one turns a one-off measurement into a permanent check, and it
is the only automated evidence that PRD §15 holds.

Marked slow and excluded from the hook, since the build takes about a
minute. Asserting on nebula.spec instead would have been fast and would
have caught none of the packaging bugs found so far, all of which
appeared only in a real bundle."
```

---

## Definition of Done

Verified against spec §12:

1. `scripts/build.sh` produces the app and the disk image — Task 3, Step 3.
2. The app launches from Finder and renders real data — Task 2, Step 5.
3. The plist carries the identifier and version — Task 2, Step 4; Task 4, Step 1.
4. A second `open` leaves one process — Task 2, Step 6; Task 4, Step 1.
5. The disk image mounts with app, symlink and instructions — Task 3, Step 4.
6. `tests/test_bundle.py` passes — Task 4, Step 2.
7. Both suites pass and the hook skips the slow test — Task 4, Steps 3 and 4.
