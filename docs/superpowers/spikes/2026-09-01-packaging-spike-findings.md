# Packaging Spike — Findings

Date: 2026-09-01
Question: can PyInstaller produce a working `Nebula.app`, and what breaks?
Answer: **yes.** A working bundle was built and verified. One source change is
required. Two of the four predicted problems were not problems.

All spike artifacts were deleted. Nothing here is committed code.

## Result

A 28MB `Nebula.app` that launches, renders the React frontend, completes the
`ui_ready` handshake, closes on the `×` button, and exits cleanly. Verified by a
self-test running *inside* the bundle:

```
SELFTEST: url      = http://127.0.0.1:57101/index.html
SELFTEST: heading  = Hello world
SELFTEST: css      = rgb(22, 22, 26)
SELFTEST: clicking close
SELFTEST: CLEAN_EXIT
```

`rgb(22, 22, 26)` is `#16161a` from `App.module.css`, so CSS Modules survive the
build. The window reported owner `Nebula` at 408x608 on layer 25.

## The one source change required

`PROJECT_ROOT = Path(__file__).resolve().parents[2]` in `src/nebula/app.py` is
wrong inside a bundle. `DIST_INDEX` and `ICON_PATH` both derive from it, so the
app exits with `Frontend not built — run 'pnpm build' in frontend/`.

It fails *loudly with the right message* rather than opening a blank window,
which is the phase 2 loud-failure design working as intended.

The fix, for the packaging phase:

```python
if hasattr(sys, "_MEIPASS"):        # running from a PyInstaller bundle
    PROJECT_ROOT = Path(sys._MEIPASS)
else:
    PROJECT_ROOT = Path(__file__).resolve().parents[2]
```

`sys._MEIPASS` resolves to `Nebula.app/Contents/Frameworks`. Both `dist/` and
`assets/Nebula.icns` were confirmed present there.

## Predictions that were wrong

**pywebview's runtime JS glob is not a problem.** `webview/util.py:352` globs
`webview/js/**/*.js` at runtime, which static analysis cannot see. PyInstaller's
contrib hooks (2026.7) ship a pywebview hook that collects them anyway — all 6
files landed in `Contents/Resources/webview/js/`. This was the main reason the
spike was recommended, and it does not exist.

**`PyObjCTest` needs no exclusion.** The spec (§10) called its 16MB "the single
biggest win". PyInstaller bundles only imported modules, and `objc` never
imports it, so it is already absent: 0 files in the bundle. That spec claim
should be dropped.

## Build-time traps

**`--add-data` resolves relative to `--specpath`, not the working directory.**
With `--specpath spike`, `--add-data "dist:dist"` looked for `spike/dist` and
failed the build. Use absolute paths.

The working invocation:

```sh
uv run --with pyinstaller pyinstaller \
  --name Nebula --windowed --noconfirm --clean \
  --paths "$PWD/src" \
  --add-data "$PWD/dist:dist" \
  --add-data "$PWD/assets/Nebula.icns:assets" \
  --icon "$PWD/assets/Nebula.icns" \
  <entry-point>.py
```

PyInstaller needs a script as its entry point, so `src/nebula/__main__.py` or a
thin launcher is required — a console-script name will not do.

## Distribution facts

| | |
|---|---|
| Size | 28MB (`Contents/Frameworks` 18MB, `Resources` 5.7MB, `MacOS` 3.6MB) |
| Architecture | `arm64` only, as expected — no Intel recipients |
| Signature | ad-hoc (PyInstaller signs automatically); not Developer ID |
| `spctl -a` | **rejected** — confirms the PRD §26 Gatekeeper block |
| `xattr -cr` | clears a quarantine flag — PRD §26 option 2 verified mechanically |

The size estimate in the spec (25-40MB) held.

## Info.plist issues to fix in the packaging phase

- `CFBundleIdentifier` is `Nebula`. It should be reverse-DNS, e.g.
  `com.giovanniiskandar.nebula`; a bare name risks collisions and is what
  macOS keys preferences and permissions off.
- `CFBundleShortVersionString` is `0.0.0`, not the `0.1.0` in `pyproject.toml`.
  Nothing wires the two together.
- `CFBundleName`, `CFBundleDisplayName` and `CFBundleIconFile` are all correct,
  so the Dock name becomes `Nebula` rather than `python3.13` — the half of the
  icon problem that could not be fixed without bundling.

## Open question not settled here

`--onedir` (used here) produces both `Nebula/` and `Nebula.app`, 54MB on disk
together. `--onefile` yields a single file but unpacks to a temp directory on
every launch, which costs startup time. Not tested; worth a measurement when
packaging is built for real.

## Recommendation

Packaging is low-risk and ready to be a normal phase. The unknowns are resolved:
one small source change, one build-time path trap, and three Info.plist values.
No spike-driven surprises remain. It does not need to happen before phase 3.
