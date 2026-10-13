import base64
import json
import os
from pathlib import Path
import sqlite3
import sys
import unittest
from unittest.mock import patch
from werkzeug.security import generate_password_hash

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'web'))
import app as web


class RoleTests(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(':memory:')
        self.conn.row_factory = sqlite3.Row
        self.db = patch.object(web.skills_db, 'get_conn', return_value=self.conn)
        self.db.start()
        web.init_users_table()
        self.env = patch.dict(os.environ, {'ADMIN_PROXY_AUTH': '1', 'ADMIN_DYNAMIC_AUTH': '1'})
        self.env.start()
        self.key = patch.object(web, '_get_admin_key_hash', return_value=generate_password_hash('gateway-test-key'))
        self.key.start()
        self.client = web.app.test_client()
        self.add('member', 0, ['skill_view'])
        self.add('manager', 1, ['skill_view'])
        # New columns are part of the required migration.
        cols = {r[1] for r in self.conn.execute('PRAGMA table_info(users)')}
        self.schema_ready = {'is_super_admin','must_change_password','hide_unauthorized'} <= cols
        if self.schema_ready:
            self.add('superAdmin', 1, ['*'], True)

    def tearDown(self):
        self.key.stop(); self.env.stop(); self.db.stop(); self.conn.close()

    def add(self, name, admin, permissions, super_admin=False):
        self.conn.execute('INSERT INTO users(username,password_hash,is_admin,status,permissions) VALUES(?,?,?,?,?)',
                          (name,generate_password_hash('RoleTest#123456'),admin,'approved',json.dumps(permissions)))
        if super_admin:
            self.conn.execute('UPDATE users SET is_super_admin=1 WHERE username=?',(name,))
        self.conn.commit()

    def headers(self, name='manager'):
        return {'X-Admin-Key':'gateway-test-key','X-Admin-User64':base64.b64encode(name.encode()).decode(),'X-Admin-Request':'1'}

    def test_schema(self):
        self.assertTrue(self.schema_ready)

    def test_empty_permissions_really_empty(self):
        self.assertEqual(web._parse_permissions('[]'), [])
        self.assertEqual(web._parse_permissions([]), [])
        self.assertEqual(web._parse_permissions('broken'), [])

    def test_admin_respects_permissions(self):
        self.assertFalse(web.has_permission({'is_admin':True,'permissions':['skill_view']},'skill_import'))
        self.assertTrue(web.has_permission({'is_super_admin':True,'permissions':[]},'skill_import'))

    def test_manager_cannot_promote(self):
        r=self.client.post('/api/super-admin/role',headers=self.headers(),json={'username':'member','role':'admin'})
        self.assertEqual(r.status_code,403)

    def test_promotion_and_demotion(self):
        self.assertTrue(self.schema_ready)
        for role in ('admin','user'):
            r=self.client.post('/api/super-admin/role',headers=self.headers('superAdmin'),json={'username':'member','role':role})
            self.assertEqual(r.status_code,200,r.get_json())
            self.assertEqual(self.conn.execute("SELECT is_admin FROM users WHERE username='member'").fetchone()[0],role=='admin')

    def test_manager_cannot_edit_other_admin(self):
        r=self.client.post('/api/admin/permissions',headers=self.headers(),json={'username':'manager','permissions':['*']})
        self.assertEqual(r.status_code,403)

    def test_assign_empty_and_hide(self):
        r=self.client.post('/api/admin/permissions',headers=self.headers(),json={'username':'member','permissions':[],'hide_unauthorized':True})
        self.assertEqual(r.status_code,200,r.get_json())
        row=self.conn.execute("SELECT permissions,hide_unauthorized FROM users WHERE username='member'").fetchone()
        self.assertEqual(json.loads(row[0]),[]);self.assertEqual(row[1],1)

    def test_visibility_only_updates_self(self):
        uid=self.conn.execute("SELECT id FROM users WHERE username='member'").fetchone()[0]
        with self.client.session_transaction() as s:s['user_id']=uid
        r=self.client.post('/api/auth/visibility',json={'hide_unauthorized':True,'username':'manager'})
        self.assertEqual(r.status_code,200)
        self.assertEqual(self.conn.execute("SELECT hide_unauthorized FROM users WHERE username='member'").fetchone()[0],1)
        self.assertEqual(self.conn.execute("SELECT hide_unauthorized FROM users WHERE username='manager'").fetchone()[0],0)

    def test_bootstrap_blocks_management(self):
        self.assertTrue(self.schema_ready)
        self.conn.execute("UPDATE users SET must_change_password=1 WHERE username='superAdmin'");self.conn.commit()
        r=self.client.get('/api/super-admin/users',headers=self.headers('superAdmin'))
        self.assertEqual(r.status_code,403);self.assertEqual(r.get_json()['code'],'password_change_required')
        r=self.client.get('/api/admin/me',headers=self.headers('superAdmin'))
        self.assertEqual(r.status_code,200);self.assertTrue(r.get_json()['user']['must_change_password'])

    def test_cannot_disable_or_demote_last_super(self):
        self.assertTrue(self.schema_ready)
        for endpoint,body in [('/api/super-admin/role',{'role':'user'}),('/api/super-admin/status',{'enabled':False})]:
            r=self.client.post(endpoint,headers=self.headers('superAdmin'),json={'username':'superAdmin',**body})
            self.assertEqual(r.status_code,409)

    def test_internal_auth_role_and_disabled_checks(self):
        self.assertTrue(self.schema_ready)
        auth='Basic '+base64.b64encode(b'manager:RoleTest#123456').decode()
        h={'X-Admin-Key':'gateway-test-key','Authorization':auth,'X-Original-URI':'/admin'}
        self.assertEqual(self.client.get('/api/internal/admin-auth',headers=h).status_code,200)
        h['X-Original-URI']='/super-admin'
        self.assertEqual(self.client.get('/api/internal/admin-auth',headers=h).status_code,401)
        h['X-Original-URI']='/admin'
        self.conn.execute("UPDATE users SET status='disabled' WHERE username='manager'");self.conn.commit()
        self.assertEqual(self.client.get('/api/internal/admin-auth',headers=h).status_code,403)
        self.assertEqual(self.client.get('/api/internal/admin-auth').status_code,401)

    def test_manager_cannot_create_admin(self):
        r=self.client.post('/api/admin/create',headers=self.headers(),json={'username':'newManager','password':'RoleTest#123456','is_admin':True})
        self.assertEqual(r.status_code,403)

    def test_seed_is_idempotent_and_password_change_required(self):
        import roles
        self.conn.execute("DELETE FROM users WHERE username='superAdmin'");self.conn.commit()
        name,created=roles.seed_super_admin(web.skills_db,'superAdmin','InitialRole#123456')
        self.assertTrue(created)
        row=self.conn.execute("SELECT * FROM users WHERE username=?",(name,)).fetchone()
        self.assertEqual(row['must_change_password'],1)
        self.conn.execute("UPDATE users SET password_hash='preserved-hash' WHERE username=?",(name,));self.conn.commit()
        self.assertFalse(roles.seed_super_admin(web.skills_db,name,'InitialRole#123456')[1])
        self.assertEqual(self.conn.execute("SELECT password_hash FROM users WHERE username=?",(name,)).fetchone()[0],'preserved-hash')

    def test_change_initial_password_and_protect_reset(self):
        self.conn.execute("UPDATE users SET must_change_password=1 WHERE username='superAdmin'");self.conn.commit()
        r=self.client.post('/api/super-admin/change-password',headers=self.headers('superAdmin'),
                           json={'old_password':'RoleTest#123456','new_password':'UpdatedRole#987654'})
        self.assertEqual(r.status_code,200,r.get_json())
        self.assertEqual(self.conn.execute("SELECT must_change_password FROM users WHERE username='superAdmin'").fetchone()[0],0)
        r=self.client.post('/api/super-admin/reset-password',headers=self.headers('superAdmin'),
                           json={'username':'manager','password':'UpdatedRole#987654'})
        self.assertEqual(r.status_code,200)
        self.assertEqual(self.conn.execute("SELECT must_change_password FROM users WHERE username='manager'").fetchone()[0],1)

    def test_admin_cannot_enable_super_or_reject_admin(self):
        r=self.client.post('/api/admin/reject',headers=self.headers(),json={'username':'superAdmin'})
        self.assertEqual(r.status_code,403)

    def test_empty_permissions_cannot_use_alternative_business_routes(self):
        self.conn.execute("UPDATE users SET permissions='[]' WHERE username='member'");self.conn.commit()
        uid=self.conn.execute("SELECT id FROM users WHERE username='member'").fetchone()[0]
        with self.client.session_transaction() as s:s['user_id']=uid
        with patch.object(web,'get_ai_recommendation') as ai:
            for path in ['/api/search/ai?q=test','/api/search/all?q=test','/api/search/github?q=test','/api/trash','/api/import/list-user']:
                self.assertEqual(self.client.get(path).status_code,403,path)
            ai.assert_not_called()

    def test_view_permission_does_not_allow_registry_export(self):
        uid=self.conn.execute("SELECT id FROM users WHERE username='member'").fetchone()[0]
        with self.client.session_transaction() as s:s['user_id']=uid
        self.assertEqual(self.client.get('/api/registry/design/test/download').status_code,403)
        self.assertEqual(self.client.get('/download/test.zip').status_code,403)

    def test_export_does_not_require_view_permission(self):
        self.conn.execute("UPDATE users SET permissions='[\"skill_export\"]' WHERE username='member'");self.conn.commit()
        uid=self.conn.execute("SELECT id FROM users WHERE username='member'").fetchone()[0]
        with self.client.session_transaction() as s:s['user_id']=uid
        with patch.object(web,'build_skills_cache',return_value=([{'name':'guide','namespace':'design'}],{},{})), \
             patch.object(web,'package_skills',return_value={'success':True}):
            self.assertEqual(self.client.post('/api/package',json={'skills':['design/guide']}).status_code,200)

    def test_dynamic_pages_and_super_aliases_enforce_role(self):
        self.assertEqual(self.client.get('/super-admin').status_code,401)
        self.assertEqual(self.client.get('/super-admin',headers=self.headers()).status_code,403)
        self.assertEqual(self.client.get('/super-admin',headers=self.headers('superAdmin')).status_code,200)
        self.assertEqual(self.client.get('/api/super-admin/me',headers=self.headers()).status_code,403)
        r=self.client.post('/api/admin/approve',headers=self.headers(),json={'username':'manager'})
        self.assertEqual(r.status_code,403)


if __name__=='__main__':unittest.main()
