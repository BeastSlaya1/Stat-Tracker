# Repair for the failed web build

Use this archive instead of the earlier Website Downloads Update ZIP.
It contains the current GitHub files plus restored folders. No live repository
or website changes have been made by this repair.

## Upload while keeping folders

1. Extract the whole ZIP to a new folder using Windows **Extract All**.
2. In GitHub, open BeastSlaya1/Stat-Tracker, choose **Add file > Upload files**,
   and drag the extracted files AND folders together into the upload area.
   Drag the folders themselves, not individual files selected from inside them.
   Alternatively, copy everything into your local repository and use GitHub
   Desktop to commit and push the changes.
3. Before committing, verify these paths appear in the upload list:
   - `packages/stc_camera_preview/pyproject.toml`
   - `web-downloads/index.html`
   - `.github/workflows/build-ios.yml`
   - `scripts/check_layout.py`
4. Commit to main. The existing web deployment starts automatically.

Do not upload the ZIP itself as the website source. Do not rename files to
names such as `main (2).py` or `pyproject (1).toml`; their folder paths distinguish
files with the same name. If GitHub reports that a folder was skipped, use the
local-repository/GitHub Desktop method so all files retain their paths.

## Cause and corrections

The failed step reported `Invalid URL 'packages/stc_camera_preview'`.
That folder was absent in the uploaded repository. Flet therefore treated the
missing local path as a package URL. The corrected package is restored at the
configured path, including its Python package and Flutter extension.

The download page files are restored under `web-downloads`, images under
`assets`, and the iPhone workflow under `.github/workflows`. The root app keeps
the already uploaded camera/pairing fixes and gains the download button from
the duplicate `main (2).py`. Existing loose copies are preserved.

The root project already contains the iOS port. Its manual iPhone/iPad build
workflow now builds from the root rather than the absent `mobile/ios` folder.
It still creates an unsigned archive; Apple signing and device testing are
required before iPhone installation.

The new layout check runs before the web build. It reports missing paths
clearly if another upload loses folder structure.

## Validation and remaining check

The camera package is checked by building its Python wheel and inspecting its
bundled Dart files. Download tests, Python syntax, TOML, and ZIP integrity/path
checks are performed locally. The complete GitHub-hosted web build must be
rerun after upload; this repair does not claim that remote build has passed.

The existing 4.0.1 Android and Windows installers do not need rebuilding for
this repository-layout repair. Keep them as Release assets, not repository files.
