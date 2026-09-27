"""Offline queue and optimistic synchronization for the shared match database."""
from __future__ import annotations
import asyncio
import copy
import json
import threading
import urllib.error
import urllib.request
import uuid


class ApiError(Exception):
    def __init__(self, status, payload):
        self.status, self.payload = status, payload
        super().__init__(payload.get("error", f"Sync error {status}"))


async def api_request(base_url, path, token="", method="GET", body=None):
    if not base_url.startswith("https://"):
        raise ValueError("The database address must start with https://")
    url = base_url.rstrip("/") + path
    headers = {"Accept": "application/json"}
    if token:
        headers["Authorization"] = "Bearer " + token
    data = None
    if body is not None:
        headers["Content-Type"] = "application/json"
        data = json.dumps(body, separators=(",", ":"))
    try:
        from pyodide.http import pyfetch
    except ImportError:
        def send():
            headers["User-Agent"] = "StatTracker/4.0.2"
            request = urllib.request.Request(url, headers=headers, method=method,
                                             data=data.encode("utf-8") if data else None)
            try:
                with urllib.request.urlopen(request, timeout=15) as response:
                    return json.load(response)
            except urllib.error.HTTPError as error:
                try:
                    payload = json.loads(error.read())
                except (ValueError, UnicodeDecodeError):
                    payload = {"error": f"Database returned HTTP {error.code}"}
                raise ApiError(error.code, payload) from error
        return await asyncio.to_thread(send)
    else:
        response = await asyncio.wait_for(pyfetch(url, method=method, headers=headers, body=data), 20)
        payload = await response.json()
        if not response.ok:
            raise ApiError(response.status, payload)
        return payload


class SyncState:
    def __init__(self, saved=None):
        self.lock = threading.RLock()
        saved = saved or {}
        self.known = copy.deepcopy(saved.get("known", {}))
        self.versions = dict(saved.get("versions", {}))
        self.pending = copy.deepcopy(saved.get("pending", {}))
        self.conflicts = copy.deepcopy(saved.get("conflicts", {}))
        self.observed = {item["id"]: item for item in self.visible()}
        self.displayed_versions = dict(self.versions)

    def reflect(self):
        """Call after the UI has adopted visible(), without treating pulls as edits."""
        with self.lock:
            self.observed = {item["id"]: item for item in self.visible()}
            self.displayed_versions = dict(self.versions)

    def export(self):
        with self.lock:
            return copy.deepcopy({"known": self.known, "versions": self.versions,
                                  "pending": self.pending, "conflicts": self.conflicts})

    def observe(self, matches):
        """Queue changes, keeping their original server revision until acknowledged."""
        with self.lock:
            current = {match["id"]: copy.deepcopy(match) for match in matches}
            before = self.observed
            for key in current.keys() | before.keys():
                if current.get(key) == before.get(key):
                    continue
                deleted = key not in current
                self.known[key] = current.get(key, before[key] if key in before else {})
                self.pending[key] = {"base_version": self.pending.get(key, {}).get(
                    "base_version", self.displayed_versions.get(key, 0)), "mutation_id": uuid.uuid4().hex,
                    "body": copy.deepcopy(self.known[key]), "deleted": deleted}
            self.observed = current

    def visible(self):
        with self.lock:
            return copy.deepcopy([body for key, body in self.known.items()
                                  if body is not None and not self.pending.get(key, {}).get("deleted")])

    def outgoing(self):
        with self.lock:
            return copy.deepcopy([(key, value) for key, value in self.pending.items()
                                  if key not in self.conflicts])

    def acknowledge(self, key, sent, version):
        with self.lock:
            self.versions[key] = version
            self.displayed_versions[key] = version
            queued = self.pending.get(key)
            if queued and queued["mutation_id"] == sent["mutation_id"]:
                self.pending.pop(key)
                self.conflicts.pop(key, None)
                if sent["deleted"]:
                    self.known[key] = None
            elif queued:
                # An edit arrived while this request was in flight.
                queued["base_version"] = version

    def receive(self, record):
        key = record["id"]
        with self.lock:
            pending = self.pending.get(key)
            if pending:
                if record.get("mutation_id") == pending["mutation_id"]:
                    self.acknowledge(key, pending, record["version"])
                elif record["version"] > pending["base_version"]:
                    self.conflicts[key] = copy.deepcopy(record)
                return
            if record["version"] >= self.versions.get(key, 0):
                self.versions[key] = record["version"]
                self.known[key] = None if record["deleted"] else copy.deepcopy(record["body"])

    def resolve(self, key, keep_copy):
        with self.lock:
            remote = self.conflicts.pop(key)
            local = self.pending.pop(key)
            self.versions[key] = remote["version"] if remote else 0
            self.known[key] = None if not remote or remote["deleted"] else copy.deepcopy(remote["body"])
            if keep_copy and not local["deleted"]:
                body = copy.deepcopy(local["body"])
                body["id"] = "match-" + uuid.uuid4().hex
                body["title"] = body.get("title", "Match") + " (offline copy)"
                new_id = body["id"]
                self.known[new_id] = body
                self.pending[new_id] = {"base_version": 0, "mutation_id": uuid.uuid4().hex,
                                        "body": copy.deepcopy(body), "deleted": False}


async def synchronize(state, base_url, token, request=api_request):
    for key, pending in state.outgoing():
        try:
            result = await request(base_url, "/matches/" + key, token, "PUT", pending)
        except ApiError as error:
            if error.status != 409:
                raise
            with state.lock:
                state.conflicts[key] = error.payload.get("current")
        else:
            state.acknowledge(key, pending, result["version"])
    after = ""
    while True:
        page = await request(base_url, "/matches?after=" + after, token)
        for record in page["records"]:
            state.receive(record)
        after = page.get("next")
        if not after:
            break
