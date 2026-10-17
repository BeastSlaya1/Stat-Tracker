import asyncio
import unittest
from cloud_sync import ApiError, SyncState, synchronize

def match(key="match-one", score=0):
    return {"id": key, "title": "SCC vs Opponent", "home_score": score,
            "home_team": {"name": "SCC"}, "away_team": {"name": "Opponent"}, "events": []}

def remote(body, version=1, deleted=False, mutation="remote-mutation-0001"):
    return {"id": body["id"], "body": body, "version": version, "deleted": deleted, "mutation_id": mutation}

class QueueTests(unittest.TestCase):
    def test_failed_network_keeps_persistable_changes(self):
        state = SyncState()
        state.observe([match()])
        async def fail(*args):
            raise OSError("offline")
        with self.assertRaises(OSError):
            asyncio.run(synchronize(state, "https://example.com", "token", fail))
        restored = SyncState(state.export())
        self.assertEqual(restored.outgoing(), state.outgoing())
        self.assertEqual(restored.visible(), [match()])

    def test_edit_during_upload_stays_queued_on_acknowledged_revision(self):
        state = SyncState()
        state.observe([match()])
        key, sent = state.outgoing()[0]
        state.observe([match(score=1)])
        state.acknowledge(key, sent, 1)
        self.assertEqual(state.pending[key]["base_version"], 1)
        self.assertEqual(state.pending[key]["body"]["home_score"], 1)

    def test_download_is_not_mistaken_for_a_local_deletion(self):
        state = SyncState()
        state.observe([match()])
        state.receive(remote(match("match-two")))
        state.observe([match(score=2)])
        self.assertNotIn("match-two", state.pending)
        self.assertEqual(len(state.visible()), 2)

    def test_edit_after_remote_pull_uses_last_displayed_revision(self):
        state = SyncState()
        state.receive(remote(match(), 1))
        state.reflect()
        state.receive(remote(match(score=2), 2))
        state.observe([match(score=1)])
        self.assertEqual(state.pending["match-one"]["base_version"], 1)

    def test_conflict_keeps_original_and_offline_copy(self):
        state = SyncState()
        state.receive(remote(match(), 1))
        state.reflect()
        state.observe([match(score=1)])
        state.receive(remote(match(score=2), 2))
        self.assertTrue(state.conflicts)
        self.assertEqual(state.visible()[0]["home_score"], 1)
        state.resolve("match-one", keep_copy=True)
        self.assertEqual(sorted(m["home_score"] for m in state.visible()), [1, 2])
        self.assertEqual(len(state.pending), 1)
        self.assertNotIn("match-one", state.pending)

    def test_remote_tombstone_does_not_delete_new_local_work(self):
        state = SyncState()
        state.receive(remote(match(), 1))
        state.reflect()
        state.observe([match(score=3)])
        state.receive(remote(match(), 2, True))
        self.assertTrue(state.conflicts)
        state.resolve("match-one", True)
        self.assertEqual(len(state.visible()), 1)
        self.assertEqual(state.visible()[0]["home_score"], 3)

    def test_deletion_survives_restart_and_is_not_requeued_after_ack(self):
        state = SyncState()
        state.receive(remote(match(), 1))
        state.reflect()
        state.observe([])
        state = SyncState(state.export())
        key, sent = state.outgoing()[0]
        self.assertTrue(sent["deleted"])
        state.acknowledge(key, sent, 2)
        state.observe([])
        self.assertEqual(state.pending, {})
        self.assertEqual(state.visible(), [])

    def test_lost_response_is_acknowledged_by_matching_mutation(self):
        state = SyncState()
        state.observe([match()])
        key, pending = state.outgoing()[0]
        state.receive(remote(match(), 1, mutation=pending["mutation_id"]))
        self.assertNotIn(key, state.pending)

    def test_api_conflict_remains_blocked_until_review(self):
        state = SyncState()
        state.observe([match()])
        async def request(base, path, token, method="GET", body=None):
            if method == "PUT":
                raise ApiError(409, {"current": remote(match(score=2), 1)})
            return {"records": [], "next": None}
        asyncio.run(synchronize(state, "https://example.com", "token", request))
        self.assertTrue(state.conflicts)
        self.assertEqual(state.outgoing(), [])

if __name__ == "__main__":
    unittest.main()
