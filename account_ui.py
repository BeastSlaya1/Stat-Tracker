"""In-app account and shared reference-table administration."""
import copy
from urllib.parse import quote
import flet as ft
from cloud_sync import api_request, ApiError

ROLE_NAMES={'admin':'Admin / creator','staff':'Staff','user':'User'}

class AccountManagementMixin:
    def _can_manage_database(self):
        return bool(self._database_token) and self._database_user.get('role') in ('admin','staff')

    def _management_error(self,error):
        return str(error) if isinstance(error,(ApiError,ValueError)) else 'Could not connect. Check your internet connection.'

    async def _open_accounts(self,_=None):
        if not self._can_manage_database():return
        try:
            result=await api_request(self._database_url,'/accounts',self._database_token)
        except Exception as error:
            self._snack(self._management_error(error));return
        admin=self._database_user.get('role')=='admin'
        rows=[]
        for item in result['accounts']:
            rows.append(ft.Row([ft.Text(f"{item['display_name']} · {ROLE_NAMES[item['role']]}\n{item['email']}"+(' · Disabled' if not item['enabled'] else ''),expand=True),
                               ft.TextButton('Manage',visible=admin,on_click=lambda _,account=item:self._edit_account(account))]))
        self.page.show_dialog(ft.AlertDialog(title=ft.Text('Accounts'),scrollable=True,
            content=ft.Container(width=540,content=ft.Column(rows or [ft.Text('No user accounts yet.')],tight=True)),
            actions=[ft.TextButton('Close',on_click=lambda _:self.page.pop_dialog()),ft.Button('Create account',on_click=self._create_account_dialog)]))

    def _account_field(self,label,**kwargs):
        return ft.TextField(label=label,on_focus=self._mark_input_focused,on_blur=self._mark_input_blurred,**kwargs)

    def _change_password_dialog(self,_=None):
        if not self._database_token:return
        token=self._database_token
        current=self._account_field('Current password',password=True,can_reveal_password=True)
        password=self._account_field('New password',password=True,can_reveal_password=True)
        confirm=self._account_field('Confirm new password',password=True,can_reveal_password=True)
        message=ft.Text('Use 12–128 characters. Other devices will be signed out; this device stays signed in.')
        async def save(_):
            if button.disabled:return
            if token!=self._database_token:
                message.value='Your account changed. Close this dialog and sign in again.';self.page.update();return
            if not current.value:
                message.value='Enter your current password.';self.page.update();return
            if not 12<=len(password.value or '')<=128:
                message.value='Use 12–128 characters for the new password.';self.page.update();return
            if password.value!=confirm.value:
                message.value='The new passwords do not match.';self.page.update();return
            button.disabled=True;cancel.disabled=True;self.page.update()
            try:
                await api_request(self._database_url,'/password',token,'POST',{'current_password':current.value,'new_password':password.value})
                current.value='';password.value='';confirm.value=''
                self.page.pop_dialog();self._snack('Password changed. Use the new password on your other devices.')
            except Exception as error:message.value=self._management_error(error)
            finally:button.disabled=False;cancel.disabled=False;self.page.update()
        button=ft.Button('Change password',on_click=save)
        cancel=ft.TextButton('Cancel',on_click=lambda _:self.page.pop_dialog())
        self.page.pop_dialog();self.page.show_dialog(ft.AlertDialog(modal=True,title=ft.Text('Change password'),scrollable=True,
            content=ft.Container(width=440,content=ft.Column([current,password,confirm,message],tight=True)),actions=[cancel,button]))

    def _create_account_dialog(self,_=None):
        if not self._can_manage_database():return
        choices=list(ROLE_NAMES) if self._database_user.get('role')=='admin' else ['user']
        name=self._account_field('Name');email=self._account_field('Email')
        password=self._account_field('Password (at least 12 characters)',password=True,can_reveal_password=True)
        role=ft.Dropdown(label='Account type',value='user',options=[ft.dropdown.Option(k,ROLE_NAMES[k]) for k in choices])
        message=ft.Text('Give the person their login details privately.')
        async def save(_):
            button.disabled=True;self.page.update()
            try:
                await api_request(self._database_url,'/accounts',self._database_token,'POST',{'display_name':name.value or '', 'email':email.value or '', 'password':password.value or '', 'role':role.value})
                password.value='';self.page.pop_dialog();self._snack('Account created. They can now sign in.');await self._open_accounts()
            except Exception as error:
                message.value=self._management_error(error)
            finally:button.disabled=False;self.page.update()
        button=ft.Button('Create account',on_click=save)
        self.page.pop_dialog()
        self.page.show_dialog(ft.AlertDialog(title=ft.Text('Create account'),scrollable=True,
            content=ft.Container(width=440,content=ft.Column([name,email,password,role,message],tight=True)),
            actions=[ft.TextButton('Cancel',on_click=lambda _:self.page.pop_dialog()),button]))

    def _edit_account(self,account):
        if self._database_user.get('role')!='admin':return
        role=ft.Dropdown(label='Account type',value=account['role'],options=[ft.dropdown.Option(k,v) for k,v in ROLE_NAMES.items()])
        enabled=ft.Checkbox(label='Account enabled',value=bool(account['enabled']))
        password=self._account_field('New password (leave empty to keep)',password=True,can_reveal_password=True)
        message=ft.Text('Saving signs this account out on its devices.')
        async def save(_):
            button.disabled=True;self.page.update()
            try:
                body={'role':role.value,'enabled':bool(enabled.value)}
                if password.value:body['password']=password.value
                await api_request(self._database_url,'/accounts/'+account['id'],self._database_token,'PUT',body)
                password.value='';self.page.pop_dialog();self._snack('Account access updated.')
            except Exception as error:message.value=self._management_error(error)
            finally:button.disabled=False;self.page.update()
        button=ft.Button('Save access',on_click=save)
        self.page.pop_dialog();self.page.show_dialog(ft.AlertDialog(title=ft.Text(account['display_name']),scrollable=True,
            content=ft.Container(width=440,content=ft.Column([ft.Text(account['email']),role,enabled,password,message],tight=True)),
            actions=[ft.TextButton('Cancel',on_click=lambda _:self.page.pop_dialog()),button]))

    async def _open_catalog_manager(self,_=None):
        if not self._can_manage_database():return
        try:result=await api_request(self._database_url,'/catalog/manage',self._database_token)
        except Exception as error:self._snack(self._management_error(error));return
        self.page.show_dialog(ft.AlertDialog(title=ft.Text('Shared database'),scrollable=True,
            content=ft.Container(width=480,content=ft.Column([ft.Text('Manage shared reference data here. Use the match selector in the workspace to edit or delete matches.')]+
                [ft.Button(f"{table['name']} ({len(table['rows'])})",on_click=lambda _,t=table:self._edit_catalog_table(t)) for table in result['tables']],tight=True)),
            actions=[ft.TextButton('Close',on_click=lambda _:self.page.pop_dialog())]))

    def _edit_catalog_table(self,table):
        rows=copy.deepcopy(table['rows']);listing=ft.Column(tight=True);message=ft.Text('Changes are shared with all accounts after saving.');offset=0
        def render():
            listing.controls=[ft.Row([ft.Text(' · '.join(str(row.get(k,'')) for k in table['fields']),expand=True),
                ft.TextButton('Edit',on_click=lambda _,i=i:edit_row(i)),ft.TextButton('Delete',on_click=lambda _,i=i:delete_row(i))]) for i,row in enumerate(rows) if offset<=i<offset+20]
            listing.controls.append(ft.Text(f'{min(offset+1,len(rows))}–{min(offset+20,len(rows))} of {len(rows)} rows'))
            self.page.update()
        def move(step):
            nonlocal offset
            offset=max(0,min(max(0,len(rows)-1)//20*20,offset+step));render()
        def delete_row(index):
            rows.pop(index);move(0)
        def edit_row(index=None):
            original=rows[index] if index is not None else {'ID':max([r['ID'] for r in rows],default=0)+1}
            fields={k:self._account_field(k,value=str(original.get(k,''))) for k in table['fields']};error=ft.Text('')
            def accept(_):
                try:
                    item={k:int(field.value) if table['fields'][k]=='number' else (field.value or '').strip() for k,field in fields.items()}
                    if item['ID']<1 or any(r['ID']==item['ID'] for i,r in enumerate(rows) if i!=index):raise ValueError('Choose a unique positive ID.')
                    if index is None:rows.append(item)
                    else:rows[index]=item
                    self.page.pop_dialog();render()
                except ValueError:error.value='Use whole numbers for numeric fields and a unique positive ID.';self.page.update()
            self.page.show_dialog(ft.AlertDialog(title=ft.Text('Edit row' if index is not None else 'Add row'),scrollable=True,
                content=ft.Container(width=400,content=ft.Column(list(fields.values())+[error],tight=True)),
                actions=[ft.TextButton('Cancel',on_click=lambda _:self.page.pop_dialog()),ft.Button('Keep row',on_click=accept)]))
        async def save(_):
            button.disabled=True;self.page.update()
            try:
                await api_request(self._database_url,'/catalog/manage/'+quote(table['name'],safe=''),self._database_token,'PUT',{'base_version':table['version'],'rows':rows})
                self._database_catalog[table['name']]=copy.deepcopy(rows);await self._persist_database()
                self.page.pop_dialog();self._snack('Shared database updated.')
            except Exception as error:message.value=self._management_error(error)
            finally:button.disabled=False;self.page.update()
        button=ft.Button('Save changes',on_click=save)
        self.page.pop_dialog();self.page.show_dialog(ft.AlertDialog(title=ft.Text(table['name']),scrollable=True,
            content=ft.Container(width=600,content=ft.Column([message,listing,ft.Row([ft.TextButton('Previous',on_click=lambda _:move(-20)),ft.TextButton('Next',on_click=lambda _:move(20)),ft.Button('Add row',on_click=lambda _:edit_row())],wrap=True)],tight=True)),
            actions=[ft.TextButton('Discard / close',on_click=lambda _:self.page.pop_dialog()),button]));render()
