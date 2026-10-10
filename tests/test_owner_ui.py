import asyncio
import unittest
from unittest.mock import Mock, AsyncMock, patch
import flet as ft
from test_app_integration import app,controls
from cloud_sync import SyncState,synchronize,ApiError

class OwnerTests(unittest.TestCase):
    def test_only_primary_owner_offers_owner_role_and_owners_offer_hidden(self):
        for role,primary in [('admin',False),('owner',False),('owner',True)]:
            a=app();a._database_user={'id':'test','role':role,'can_grant_owner':primary}
            a._create_account_dialog();items=list(controls(a.page.dialog))
            roles=next(c for c in items if isinstance(c,ft.Dropdown) and c.label=='Account type')
            hidden=next(c for c in items if isinstance(c,ft.Checkbox) and c.label=='Hidden account')
            self.assertEqual('owner' in [o.key for o in roles.options],primary)
            self.assertEqual(hidden.visible,role=='owner')

    def test_scope_refresh_removes_old_synced_records_but_keeps_new_offline_matches(self):
        state=SyncState({'known':{'old':{'id':'old'},'new':{'id':'new'}},'versions':{'old':1}})
        async def request(*args):return {'records':[],'next':None,'visibility_complete':True}
        removed=asyncio.run(synchronize(state,'https://test','token',request))
        self.assertEqual(removed,{'old'});self.assertEqual(state.visible(),[{'id':'new'}])

    def test_rejected_private_edit_cannot_reappear_as_a_conflict_copy(self):
        state=SyncState({'known':{'old':{'id':'old'}},'versions':{'old':1},'pending':{'old':{'base_version':1,'mutation_id':'change','body':{'id':'old'},'deleted':False}}})
        async def request(url,path,token,*args):
            if args:raise ApiError(404,{'error':'Match not found.'})
            return {'records':[],'next':None,'visibility_complete':True}
        self.assertEqual(asyncio.run(synchronize(state,'https://test','token',request)),{'old'})
        self.assertFalse(state.known);self.assertFalse(state.conflicts);self.assertFalse(state.pending)

    def test_login_validates_cached_scope_without_discarding_offline_edits(self):
        a=app();a._database=None;a._database_busy=False;a._save=Mock()
        a._persist_database=AsyncMock()
        a._database_accounts={'same:user':{'role':'user','hidden':False,'state':{'known':{'offline':{'id':'offline'}}}}}
        seen=[]
        async def refresh(state,*args):
            seen.extend(state.visible())
            return set()
        with patch('database_ui.synchronize',side_effect=refresh),patch('database_ui.api_request',new=AsyncMock(return_value={})),patch('database_ui.Match.from_dict',side_effect=lambda x:x):
            asyncio.run(a._accept_database_login('https://test',{'token':'new','user':{'id':'same','role':'user','visibility_version':1}}))
        self.assertEqual(seen,[{'id':'offline'}])
        self.assertEqual(a.matches,seen)

    def test_failed_login_scope_refresh_preserves_previous_account(self):
        a=app();a._database=SyncState();a._database_busy=False
        previous=dict(a._database_user)
        with patch('database_ui.synchronize',new=AsyncMock(side_effect=ApiError(503,{'error':'Offline'}))):
            with self.assertRaises(ApiError):
                asyncio.run(a._accept_database_login('https://test',{'token':'new','user':{'id':'same','role':'user','visibility_version':1}}))
        self.assertEqual(a._database_user,previous)
