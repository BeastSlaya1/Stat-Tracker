"""Staff sign-in and automatic shared-database sync for desktop, mobile and web."""
import asyncio
import json
import time
from pathlib import Path
from urllib.parse import urlparse
import flet as ft
from cloud_sync import ApiError, SyncState, api_request, synchronize, match_content
from models import Match
from account_ui import AccountManagementMixin, ROLE_NAMES
from game_browser import GameBrowserMixin
from security_ui import SecurityMixin
from auth0_ui import Auth0Mixin

DATABASE_PREFS_KEY = "stat_tracker_shared_database_v1"


class DatabaseSyncMixin(GameBrowserMixin, AccountManagementMixin, SecurityMixin, Auth0Mixin):
    def _init_database_sync(self):
        self._database = None
        self._database_accounts = {}
        self._fixture_workspaces = {}
        self._coach_preferences = {}
        self._database_ready = False
        self._database_url = "https://stat-tracker-sync.joshuapieterse1.workers.dev"
        self._database_token = ""
        self._database_user = {}
        self._database_catalog = {}
        try:
            self._database_catalog = json.loads(Path(__file__).with_name("reference_data.json").read_text(encoding="utf-8"))
        except (OSError, ValueError):
            pass
        self._database_busy = False
        self._database_transition = False
        self._database_last_catalog = 0
        self._database_persist_lock = asyncio.Lock()
        self._database_status = ft.Text("Database: not connected", size=11, color="#94a3b8")
        self._database_prefs = self._web_prefs
        if self._database_prefs is None:
            self._database_prefs = ft.SharedPreferences()
            self.page.services.append(self._database_prefs)

    def _stash_database_account(self):
        user=self._database_user
        if user.get('id') and self._database is not None:
            self._database.observe([m.to_dict() for m in self.matches])
            self._database_accounts[user['id']+':'+str(user.get('role','staff'))]={'role':user.get('role'), 'state':self._database.export()}

    def _database_school_names(self):
        rows = self._database_catalog.get("Schools", [])
        names = []
        seen = set()
        for row in rows:
            name = (row.get("School_ID") or "").strip()
            # Repair the legacy combined choice even when supplied by saved/server data.
            choices = ("St Stithians College", "Kearsney") if name.casefold() == "st stithians collegekearsney" else (name,)
            for choice in choices:
                key = choice.casefold()
                if key and key != "st charles college" and key not in seen:
                    names.append(choice)
                    seen.add(key)
        return names or None

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
                "state": self._database.export(), "accounts": self._database_accounts, "fixture_workspaces": getattr(self,"_fixture_workspaces",{}), "coach_preferences": getattr(self,"_coach_preferences",{}), "saved_at": time.time_ns()}

    def _database_changed(self):
        if self._database is not None:
            for match in self.matches:
                before = self._database.observed.get(match.id)
                if self._database_token and match_content(match.to_dict()) != match_content(before):
                    if before is None:
                        match.created_by_id = self._database_user.get('id','')
                        match.created_by_name = self._database_user.get('display_name','')
                    match.edited_by_id = self._database_user.get('id','')
                    match.edited_by_name = self._database_user.get('display_name','')
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
            self._database_accounts = saved.get('accounts', {})
            self._fixture_workspaces = saved.get('fixture_workspaces', {})
            self._coach_preferences = saved.get('coach_preferences', {})
            self._database = SyncState(saved.get("state"))
            if not self._database_user.get('id'):
                # Preserve pre-account local work for the administrator, not the next ordinary user.
                if self.matches and not self._database.known:
                    self._database.observe([m.to_dict() for m in self.matches])
                if self._database.known:self._database_accounts['legacy']={'role':'admin','state':self._database.export()}
                self._database=SyncState();self.matches=[]
            self._database_ready = True
            if self._database.known:
                # The durable queue contains the latest local changes, even if
                # a previous process exited between its two persistence writes.
                self.matches = [Match.from_dict(item) for item in self._database.visible()]
                self._full_refresh()
            else:
                self._database.observe([match.to_dict() for match in self.matches])
            self._full_refresh()
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
        if self._database_busy or self._database_transition or self._database is None:
            return
        if not self._database_url or not self._database_token:
            self._database_message("Database: sign in to sync")
            return
        self._database_busy = True
        try:
            profile = (await api_request(self._database_url, '/me', self._database_token))['user']
            if profile['role']=='user' and self._database_user.get('role') not in (None,'user'):
                self._stash_database_account()
                self._database = SyncState();self.matches=[]
            if profile['role']=='coach':
                self._database=SyncState();self.matches=[];self.active_match_idx=-1
            profile_changed = self._database_user != profile
            self._database_user = profile
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
            self.active_match_idx = next((i for i,m in enumerate(updated) if m.id == selected), -1)
            if changed:
                from storage import save_matches
                save_matches(self.matches)
                if self.is_web:
                    await self._save_web_async()
            if changed or profile_changed:
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
                self._stash_database_account()
                self._database_token = ""
                self._database_user = {}
                self._database = SyncState();self.matches=[]
                self._save();self._full_refresh()
                await self._persist_database()
                self._database_message("Session expired — sign in again; offline changes are saved.")
            else:
                self._database_message(str(error))
        finally:
            self._database_busy = False

    async def _accept_database_login(self, address, result):
        while self._database_busy:await asyncio.sleep(.05)
        self._timer_running=False
        if getattr(self, 'camera_on', False):self._stop_camera()
        self._stash_database_account()
        self._database_url = address
        self._database_token = result["token"]
        self._database_user = result["user"]
        cached = self._database_accounts.get(result['user']['id']+':'+result['user']['role'],self._database_accounts.get(result['user']['id'], {}))
        if not cached and result['user']['role'] in ('admin','staff'):
            cached=next((self._database_accounts[k] for k in (result['user']['id']+':admin',result['user']['id']+':staff',result['user']['id']+':user') if k in self._database_accounts),{})
        if not cached and result['user']['role']=='admin':cached=self._database_accounts.pop('legacy', {})
        if result['user']['role']=='user' and cached.get('role') not in (None,'user'):cached={}
        if result['user']['role']=='coach': cached={}
        self._database=SyncState(cached.get('state'))
        self.matches=[Match.from_dict(item) for item in self._database.visible()]
        self.active_match_idx=-1
        self._save();self._full_refresh()
        self._database_catalog = await api_request(address, "/catalog", self._database_token)
        await self._persist_database()

    async def _check_signin_method(self, method):
        try:
            capabilities = await api_request(self._database_url, "/signin/methods")
        except ApiError as error:
            if error.status in (401, 404, 405):
                raise ApiError(503, {"error": "The account server needs the sign-in update. In GitHub, run Actions → Deploy account and sync server. Password sign-in remains available."}) from error
            raise
        if not capabilities.get(method):
            raise ApiError(503, {"error": "This sign-in method is awaiting server setup. Use password sign-in for now."})

    def _open_database_dialog(self, _=None):
        email = ft.TextField(label="Email", value=self._database_user.get("email", ""),
                             on_focus=self._mark_input_focused, on_blur=self._mark_input_blurred)
        password = ft.TextField(label="Password", password=True, can_reveal_password=True,
                                on_focus=self._mark_input_focused, on_blur=self._mark_input_blurred)
        message = ft.Text("Use the account provided by your administrator.", size=12)

        two_factor = ft.TextField(label="Authenticator or recovery code (if enabled)",
            on_focus=self._mark_input_focused, on_blur=self._mark_input_blurred)

        challenge = None
        delivery_code = ft.TextField(label="Email or SMS verification code", visible=False,
            on_focus=self._mark_input_focused, on_blur=self._mark_input_blurred)
        async def send_code(_):
            nonlocal challenge
            challenge = None
            send_button.disabled = True
            self.page.update()
            selected = (email.value or "", method.value)
            try:
                await self._check_signin_method(selected[1])
                result = await api_request(self._database_url, "/signin/start", method="POST",
                    body={"email": selected[0], "channel": selected[1]})
                if selected != (email.value or "", method.value):
                    return
                challenge = result["challenge"]
                message.value = result["message"]
            except Exception as error:
                message.value = str(error) if isinstance(error, ApiError) else "Could not send a code. Try again."
            finally:
                send_button.disabled = False
                self.page.update()
        def changed(_):
            nonlocal challenge
            challenge = None
            password.value = two_factor.value = delivery_code.value = ""
            password.visible = method.value == "password"
            delivery_code.visible = send_button.visible = method.value in ("email", "sms")
            two_factor.label = "Authenticator code" if method.value == "authenticator" else "Authenticator or recovery code (if enabled)"
            message.value = ("Enable authenticator sign-in in Profile and security → Manage sign-in methods first. Use a fresh code; setup codes cannot be reused." if method.value == "authenticator" else
                "Email/SMS sign-in needs administrator setup and a verified contact in Profile and security." if method.value in ("email", "sms") else
                "Use your password and an authenticator code if 2FA is enabled.")
            self.page.update()
        method = ft.Dropdown(label="Sign-in method", value="password", options=[
            ft.dropdown.Option("password", "Password"),
            ft.dropdown.Option("authenticator", "Authenticator app"),
            ft.dropdown.Option("email", "Email code"),
            ft.dropdown.Option("sms", "SMS code"),
        ], on_select=changed)
        email.on_change = changed
        send_button = ft.Button("Send code", on_click=send_code, visible=False)

        async def sign_in(_):
            address = self._database_url.rstrip("/")
            parsed = urlparse(address)
            if parsed.scheme != "https" or not parsed.netloc or parsed.username or parsed.password or parsed.query or parsed.fragment:
                message.value = "The database connection is unavailable. Contact your administrator."
                self.page.update()
                return
            if self._database_url and address != self._database_url and self._database and self._database.known:
                message.value = "This device already has data for another database. Export it before changing databases."
                self.page.update()
                return
            if self._database_transition:return
            self._database_transition=True
            try:
                payload = {"email": email.value or "", "code": (two_factor.value or "").strip()}
                endpoint = "/login"
                if method.value == "password":
                    payload["password"] = password.value or ""
                elif method.value == "authenticator":
                    endpoint = "/signin/authenticator"
                else:
                    if not challenge:
                        message.value = "Choose Send code first."
                        self.page.update()
                        return
                    endpoint = "/signin/check"
                    payload.update(challenge=challenge, verification_code=(delivery_code.value or "").strip())
                if method.value != "password":
                    await self._check_signin_method(method.value)
                result = await api_request(address, endpoint, method="POST", body=payload)
                await self._accept_database_login(address, result)
                password.value = ""
                two_factor.value = ""
                self.page.pop_dialog()
                self._database_transition=False
                await self._sync_database_once()
            except Exception as error:
                message.value = str(error) if isinstance(error, ApiError) else "Could not connect. Check your internet connection."
                self.page.update()
            finally:
                self._database_transition=False

        async def sign_out(_):
            if self._database_transition:return
            self._database_transition=True
            try:
                while self._database_busy:await asyncio.sleep(.05)
                self._stash_database_account()
                self._timer_running=False
                if getattr(self, 'camera_on', False):self._stop_camera()
                try:
                    if self._database_token:
                        await api_request(self._database_url, '/logout', self._database_token, 'POST', {})
                except Exception:pass
                self._database_token='';self._database_user={}
                self._database=SyncState();self.matches=[];self.active_match_idx=-1
                self._save();self._full_refresh()
                await self._persist_database()
                self.page.pop_dialog()
                self._database_message('Signed out. Saved work is kept separately for each account.')
            finally:self._database_transition=False

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
        content = [method, email, password, send_button, delivery_code, two_factor, message]
        if self._database_token:
            content.append(ft.Button('Browse saved games',on_click=self._open_saved_games))
            content.insert(0,ft.Text(f"{self._database_user.get('display_name','')} · {ROLE_NAMES.get(self._database_user.get('role'),'Account')}"))
        if self._database_token:content.append(ft.Button('Profile and security',on_click=self._open_security_dialog))
        if self._database_token:content.append(ft.Button('Change password',on_click=self._change_password_dialog))
        if self._can_manage_database():
            content += [ft.Button('Manage accounts',on_click=self._open_accounts),ft.Button('Manage shared database',on_click=self._open_catalog_manager)]
        if conflict_count:
            content += [ft.Text(f"{conflict_count} match(es) were changed by another device. Keep both versions to review them without losing work."),
                        ft.Button("Keep both versions", on_click=keep_copies)]
        self.page.show_dialog(ft.AlertDialog(title=ft.Text("Account and database"),scrollable=True,
            content=ft.Container(width=420, content=ft.Column(content, tight=True, scroll=ft.ScrollMode.AUTO)),
            actions=[ft.TextButton("Close", on_click=lambda _: self.page.pop_dialog()),
                     ft.TextButton("Sign out", on_click=sign_out, visible=bool(self._database_token)),
                     ft.Button("Sign in", on_click=sign_in)]))
