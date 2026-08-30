"""
StatTracker AI — Storage (JSON persistence)
Saves / loads match data and app settings from local JSON files.
"""
from __future__ import annotations
import json, os, shutil, sys, tempfile, threading, time
from typing import List, Optional
from models import Match


def _data_dir() -> str:
    """Where match data / settings actually get saved.

    On Windows this MUST be a per-user writable location, not the folder
    the app itself lives in — a properly installed app lives in
    Program Files, which normal (non-admin) usage cannot write to at all.
    Saving next to the app's own files worked fine for the old
    "unzip a folder, run the exe from wherever you put it" distribution,
    but silently breaks the moment the app is installed properly (e.g.
    via the Inno Setup installer under installer/StatTracker.iss) —
    every save would fail with no obvious error for the person using it.

    %LOCALAPPDATA%\\Stat Tracker is the standard, always-writable location
    Windows apps use for exactly this. Every other platform keeps the
    previous behavior (saving next to the app's own files) since that
    already works correctly there — Android's app data directory is
    writable by design, and desktop dev/testing on macOS/Linux was never
    affected by this issue in the first place.
    """
    if sys.platform == "win32":
        base = os.getenv("LOCALAPPDATA") or os.path.expanduser("~")
        d = os.path.join(base, "Stat Tracker")
        os.makedirs(d, exist_ok=True)
        return d
    return os.path.dirname(__file__)


SAVE_FILE = os.path.join(_data_dir(), "stattracker_data.json")
SETTINGS_FILE = os.path.join(_data_dir(), "stattracker_settings.json")

# Guards against two threads (e.g. the autosave loop and a UI action) writing
# the save file at the same time, which produced interleaved/duplicated JSON
# content — the actual cause of "Extra data: line N column N" load errors.
_save_lock = threading.Lock()


def _atomic_write_json(path: str, data) -> None:
    """Write JSON to a temp file, then atomically replace the target file.
    This means a crash or power loss mid-write can never leave a corrupted
    half-written file in place — the old file stays intact until the new
    one is fully written and flushed."""
    directory = os.path.dirname(path) or "."
    fd, tmp_path = tempfile.mkstemp(dir=directory, prefix=".tmp_", suffix=".json")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_path, path)   # atomic on both Windows and POSIX
    except Exception:
        try: os.remove(tmp_path)
        except Exception: pass
        raise


def save_matches(matches: List[Match]) -> None:
    try:
        with _save_lock:
            _atomic_write_json(SAVE_FILE, [m.to_dict() for m in matches])
    except Exception as e:
        print(f"[Storage] Save failed: {e}")


def load_matches() -> List[Match]:
    if not os.path.exists(SAVE_FILE):
        return []
    try:
        with open(SAVE_FILE, "r", encoding="utf-8") as f:
            raw = json.load(f)
        return [Match.from_dict(d) for d in raw]
    except Exception as e:
        # Don't just silently return an empty list — that reads as "all
        # your matches vanished" with no explanation. Back up whatever is
        # there (in case it's partially recoverable) and say so clearly.
        backup_path = f"{SAVE_FILE}.corrupt-{int(time.time())}"
        try:
            shutil.copy2(SAVE_FILE, backup_path)
            print(f"[Storage] Load failed ({e}). Backed up unreadable file to: {backup_path}")
        except Exception:
            print(f"[Storage] Load failed ({e}). Could not create a backup copy.")
        return []


def save_settings(settings: dict) -> None:
    try:
        with _save_lock:
            _atomic_write_json(SETTINGS_FILE, settings)
    except Exception as e:
        print(f"[Storage] Settings save failed: {e}")


def load_settings() -> dict:
    if not os.path.exists(SETTINGS_FILE):
        return {}
    try:
        with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"[Storage] Settings load failed: {e}")
        return {}


def get_logger_name() -> Optional[str]:
    return load_settings().get("logger_name")


def set_logger_name(name: str) -> None:
    s = load_settings()
    s["logger_name"] = name
    save_settings(s)


def get_app_mode() -> Optional[str]:
    """Returns 'inputter' or 'camera', or None if never chosen."""
    return load_settings().get("app_mode")


def set_app_mode(mode: str) -> None:
    s = load_settings()
    s["app_mode"] = mode
    save_settings(s)
