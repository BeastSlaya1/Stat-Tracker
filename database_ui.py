"""Staff sign-in and automatic shared-database sync for desktop, mobile and web."""
import asyncio
import json
import time
from pathlib import Path
from urllib.parse import urlparse
import flet as ft
from cloud_sync import ApiError, SyncState, api_request, synchronize
from models import Match

DATABASE_PREFS_KEY = "stat_tracker_shared_database_v1"


class DatabaseSyncMixin:
    def _init_database_sync(self):
        self._database = None
        self._database_url = "https://stat-tracker-sync.joshuapieterse1.workers.dev"
        self._database_token = ""
        self._database_user = {}
        self._database_catalog = {}
        try:
            self._database_catalog = json.loads(Path(__file__).with_name("reference_data.json").read_text(encoding="utf-8"))
        except (OSError, ValueError):
            pass
        self._database_busy = False
        self._database_last_catalog = 0
        self._database_persist_lock = asyncio.Lock()
        self._database_status = ft.Text("Database: not connected", size=11, color="#94a3b8")
        self._database_prefs = self._web_prefs
        if self._database_prefs is None:
            self._database_prefs = ft.SharedPreferences()
            self.page.services.append(self._database_prefs)

    def _database_school_names(self):
        rows = self._database_catalog.get("Schools", [])
        return [row["School_ID"] for row in rows if row.get("School_ID")
                and row["School_ID"].lower() != "st charles college"] or None

    def _database_message(self, text):
        self._database_status.value = text
        try:
            self._database_status.update()
        except Exception:
            pass

    async def _persist_database(self):
        if self._database is None:
            return
        async with self._database_persist_lock:
            payload = self._database_payload()
            try:
                if self.is_web:
                    await self._database_prefs.set(DATABASE_PREFS_KEY, json.dumps(payload))
                else:
                    from storage import save_sync_state
                    save_sync_state(payload)
            except Exception:
                self._database_message("Could not save the offline sync queue on this device.")
                raise

    def _database_payload(self):
        if self._database is None:
            return None
        return {"url": self._database_url, "token": self._database_token,
                "user": self._database_user, "catalog": self._database_catalog,
                "state": self._database.export(), "saved_at": time.time_ns()}

    def _database_changed(self):
        if self._database is not None:
            self._database.observe([match.to_dict() for match in self.matches])
            if self.is_web:
                self.page.run_task(self._persist_database)
            else:
                from storage import save_sync_state
                try:
                    save_sync_state(self._database_payload())
                except OSError:
                    self._database_message("Could not save the offline queue. Keep the app open and retry.")

    async def _database_loop(self):
        while not getattr(self, "_web_loaded", False):
            await asyncio.sleep(0.1)
        try:
            if self.is_web:
                raw = await self._database_prefs.get(DATABASE_PREFS_KEY)
                saved = json.loads(raw) if raw else {}
                together = getattr(self, "_loaded_database", None) or {}
                if together.get("saved_at", 0) > saved.get("saved_at", 0):
                    saved = together
            else:
                from storage import load_sync_state
                saved = load_sync_state()
            self._database_url = saved.get("url") or self._database_url
            self._database_token = saved.get("token", "")
            self._database_user = saved.get("user", {})
            self._database_catalog = saved.get("catalog") or self._database_catalog
            self._database = SyncState(saved.get("state"))
            if self._database.known:
                # The durable queue contains the latest local changes, even if
                # a previous process exited between its two persistence writes.
                self.matches = [Match.from_dict(item) for item in self._database.visible()]
                self._full_refresh()
            else:
                self._database.observe([match.to_dict() for match in self.matches])
        except Exception:
            self._database_message("Could not load the offline database queue. Restart to retry.")
            return
        while True:
            try:
                await self._sync_database_once()
            except Exception:
                self._database_message("Offline — changes stay on this device and will retry.")
            await asyncio.sleep(15)

    async def _sync_database_once(self):
        if self._database_busy or self._database is None:
            return
        if not self._database_url or not self._database_token:
            self._database_message("Database: sign in to sync")
            return
        self._database_busy = True
        try:
            self._database.observe([match.to_dict() for match in self.matches])
            await self._persist_database()
            self._database_message("Syncing shared database…")
            await synchronize(self._database, self._database_url, self._database_token)
            self._database.observe([match.to_dict() for match in self.matches])
            # Capture edits made while network requests were in flight. Those
            # handlers call _database_changed and are already in the queue.
            selected = self.match.id if self.match else None
            updated = [Match.from_dict(item) for item in self._database.visible()]
            changed = [m.to_dict() for m in updated] != [m.to_dict() for m in self.matches]
            self.matches = updated
            self._database.reflect()
            self.active_match_idx = next((i for i,m in enumerate(updated) if m.id == selected), 0)
            if changed:
                from storage import save_matches
                save_matches(self.matches)
                if self.is_web:
                    await self._save_web_async()
                self._full_refresh()
            await self._persist_database()
            if time.monotonic() - self._database_last_catalog > 300:
                self._database_catalog = await api_request(self._database_url, "/catalog", self._database_token)
                self._database_last_catalog = time.monotonic()
                await self._persist_database()
            count = len(self._database.conflicts)
            pending = len(self._database.pending)
            self._database_message(f"{count} match conflict(s) — open Database" if count else
                                   f"{pending} change(s) waiting to sync" if pending else "Database up to date")
        except ApiError as error:
            if error.status == 401:
                self._database_token = ""
                await self._persist_database()
                self._database_message("Session expired — sign in again; offline changes are saved.")
            else:
                self._database_message(str(error))
        finally:
            self._database_busy = False

    def _open_database_dialog(self, _=None):
        url = ft.TextField(label="Shared database address", value=self._database_url,
                           hint_text="https://stat-tracker-sync.your-account.workers.dev",
                           on_focus=self._mark_input_focused, on_blur=self._mark_input_blurred)
        email = ft.TextField(label="Staff email", value=self._database_user.get("email", ""),
                             on_focus=self._mark_input_focused, on_blur=self._mark_input_blurred)
        password = ft.TextField(label="Password", password=True, can_reveal_password=True,
                                on_focus=self._mark_input_focused, on_blur=self._mark_input_blurred)
        message = ft.Text("Use the staff account provided by your administrator.", size=12)

        async def sign_in(_):
            address = (url.value or "").strip().rstrip("/")
            parsed = urlparse(address)
            if parsed.scheme != "https" or not parsed.netloc or parsed.username or parsed.password or parsed.query or parsed.fragment:
                message.value = "Enter the HTTPS address supplied by your administrator."
                self.page.update()
                return
            if self._database_url and address != self._database_url and self._database and self._database.known:
                message.value = "This device already has data for another database. Export it before changing databases."
                self.page.update()
                return
            try:
                result = await api_request(address, "/login", method="POST",
                                           body={"email": email.value or "", "password": password.value or ""})
                self._database_url = address
                self._database_token = result["token"]
                self._database_user = result["user"]
                password.value = ""
                self._database_catalog = await api_request(address, "/catalog", self._database_token)
                await self._persist_database()
                self.page.pop_dialog()
                await self._sync_database_once()
            except Exception as error:
                message.value = str(error) if isinstance(error, ApiError) else "Could not connect. Check the address and internet connection."
                self.page.update()

        async def sign_out(_):
            try:
                if self._database_token:
                    await api_request(self._database_url, "/logout", self._database_token, "POST", {})
            except Exception:
                pass
            self._database_token = ""
            self._database_user = {}
            await self._persist_database()
            self.page.pop_dialog()
            self._database_message("Signed out — local match data remains on this device.")

        async def keep_copies(_):
            if self._database:
                for key in list(self._database.conflicts):
                    self._database.resolve(key, keep_copy=True)
                self.matches = [Match.from_dict(item) for item in self._database.visible()]
                self._database.reflect()
                self._save()
                await self._persist_database()
                self._full_refresh()
            self.page.pop_dialog()

        conflict_count = len(self._database.conflicts) if self._database else 0
        content = [url, email, password, message]
        if conflict_count:
            content += [ft.Text(f"{conflict_count} match(es) were changed by another device. Keep both versions to review them without losing work."),
                        ft.Button("Keep both versions", on_click=keep_copies)]
        self.page.show_dialog(ft.AlertDialog(title=ft.Text("Shared database"),
            content=ft.Container(width=420, content=ft.Column(content, tight=True, scroll=ft.ScrollMode.AUTO)),
            actions=[ft.TextButton("Close", on_click=lambda _: self.page.pop_dialog()),
                     ft.TextButton("Sign out", on_click=sign_out, visible=bool(self._database_token)),
                     ft.Button("Sign in", on_click=sign_in)]))
