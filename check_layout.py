"""Check upload structure before Flet installs local dependencies."""
from pathlib import Path
import sys
import tomllib


def main():
    root = Path(__file__).resolve().parents[1]
    required = [
        "main.py", "pyproject.toml",
        "packages/stc_camera_preview/pyproject.toml",
        "packages/stc_camera_preview/stc_camera_preview/__init__.py",
        "packages/stc_camera_preview/stc_camera_preview/camera_preview.py",
        "packages/stc_camera_preview/flutter/stc_camera_preview/pubspec.yaml",
        "packages/stc_camera_preview/flutter/stc_camera_preview/lib/stc_camera_preview.dart",
        "packages/stc_camera_preview/flutter/stc_camera_preview/lib/src/extension.dart",
        "packages/stc_camera_preview/flutter/stc_camera_preview/lib/src/camera_preview.dart",
        "packages/stc_camera_preview/flutter/stc_camera_preview/lib/src/bgra_frame.dart",
        "web-downloads/index.html", "web-downloads/config.js",
        "web-downloads/styles.css", "web-downloads/downloads.js",
    ]
    missing = [name for name in required if not (root / name).is_file()]
    if missing:
        print("Required folders/files are missing. Preserve folders when uploading:")
        print("\n".join(f"  {name}" for name in missing))
        return 1
    config = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8-sig"))
    location = config["tool"]["flet"]["dev_packages"]["stc-camera-preview"]
    package = (root / location).resolve()
    if not (package / "pyproject.toml").is_file():
        print(f"Camera package cannot be found at: {package}")
        return 1
    print(f"Camera dependency resolves to: {package.as_uri()}")
    print("Camera package and download page layout OK.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
