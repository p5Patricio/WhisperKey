---
name: windows-release-pipeline
description: "End-to-end release procedure for WhisperKey on Windows. Trigger: cutting a release, bumping the version, building the installer, publishing to GitHub Releases, or updating the landing page download links."
metadata:
  author: WhisperKey
  version: "1.0"
---

## When to Use

Load this skill when shipping a version: version bumps, PyInstaller/Inno builds,
GitHub Releases, in-app updates, or the `docs/` landing page.

## The version lives in four places

A release is only consistent when all four agree:

| File | Field |
| --- | --- |
| `whisperkey/version.py` | `__version__` — what the running app reports |
| `installer/whisperkey.iss` | `MyAppVersion` — what Add/Remove Programs shows |
| `web/src/App.tsx` | `FALLBACK_VERSION` — shown if the GitHub API call fails |
| GitHub Release | `tag_name` — what `updater.check_update()` compares against |

`check_update()` compares numeric tuples of `tag_name` against `__version__`. A
tag that does not parse as digits (`v1.3.0-beta`) compares as an empty tuple and
**no user is ever offered the update**. Keep tags strictly `vMAJOR.MINOR.PATCH`.

## Build order

```bash
installer/build.bat
```

Runs `tools/build.py` (PyInstaller, driven by `WhisperKey.spec`), then locates
`ISCC.exe` and compiles `installer/whisperkey.iss` into
`dist/WhisperKey-Setup.exe`.

Inno Setup installed per-user via winget lands in
`%LOCALAPPDATA%\Programs\Inno Setup 6`, not in Program Files. `build.bat` already
probes both.

`WhisperKey.spec` bundles `build/engine-cpu/Release` as `assets/bin`. Rebuild the
engine directory *before* PyInstaller runs or you ship yesterday's binary — see
`whisper-engine-contract`.

## The SHA256 asset is not optional

`updater._get_installer_url_and_hash()` looks for a release asset whose name ends
in `.sha256`. When that asset is missing it returns an empty hash, and
`_on_update_now()` skips verification entirely — downloading and executing an
installer with **no integrity check**, silently.

Every release publishes two assets:

```bash
sha256sum dist/WhisperKey-Setup.exe > dist/WhisperKey-Setup.exe.sha256
gh release create vX.Y.Z dist/WhisperKey-Setup.exe dist/WhisperKey-Setup.exe.sha256 --title "..." --notes-file CHANGELOG-vX.Y.Z.md
```

Missing hash file means every existing user auto-updates unverified. Do not ship
a release without it.

## The landing page is served from docs/

`web/vite.config.ts` sets `outDir: '../docs'` and GitHub Pages serves `docs/`.
The site fetches the latest release from the GitHub API at runtime, so download
links follow new releases automatically — **but only after `docs/` is rebuilt and
committed**. Editing `web/src` alone changes nothing that users can see.

```bash
cd web && pnpm install && pnpm build   # writes ../docs
git add docs web && git commit
```

`emptyOutDir: false` — Vite will not clear `docs/`, so stale assets survive
rebuilds. Check `git status` after building and remove orphans deliberately.

## Verify the two paths users actually take

A release is not done until both are confirmed:

1. **Fresh install** — the landing page button resolves to the new
   `WhisperKey-Setup.exe` (check the GitHub API response the page consumes, not
   just the fallback URL).
2. **Existing install** — `check_update()` against the published tag returns
   `is_newer=True` for the *previous* version, and the `.sha256` asset resolves.

Verify these against the published release, not against local files.
