"""Restore OpenCV's dynamically read configuration after Flet bytecode packaging.
Usage: python scripts/finalize_windows.py path/to/opencv_python-version.whl
"""
import argparse
import email
from pathlib import Path
import zipfile

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('wheel', type=Path)
parser.add_argument('--bundle', type=Path, default=Path('build/windows'))
args = parser.parse_args()
installed = next((args.bundle/'site-packages').glob('opencv_python-*.dist-info/METADATA'))
installed_version = email.message_from_string(installed.read_text(encoding='utf-8'))['Version']
with zipfile.ZipFile(args.wheel) as archive:
    metadata = next(n for n in archive.namelist() if n.startswith('opencv_python-') and n.endswith('.dist-info/METADATA'))
    version = email.message_from_bytes(archive.read(metadata))['Version']
    if version != installed_version:
        raise SystemExit(f'Wheel version {version} does not match bundled OpenCV {installed_version}')
    for name in ('cv2/config.py', 'cv2/config-3.py'):
        target = args.bundle/'site-packages'/name
        target.write_bytes(archive.read(name))
        print(f'Restored {name} from OpenCV {version}')
