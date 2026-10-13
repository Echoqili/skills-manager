"""Nginx 独立管理员入口：普通会话不能绕过代理认证，写操作必须带专用请求头。"""
import os
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'web'))
import app as web
from werkzeug.security import generate_password_hash


class AdminProxyTests(unittest.TestCase):
    def setUp(self):
        self.env = patch.dict(os.environ, {'ADMIN_PROXY_AUTH': '1'})
        self.env.start()
        self.admin = patch.object(web, 'get_current_user', return_value={'id': 1, 'username': 'admin', 'is_admin': True})
        self.admin.start()
        self.key = 'server-only-test-key'
        self.hash = patch.object(web, '_get_admin_key_hash', return_value=generate_password_hash(self.key))
        self.hash.start()
        self.mail = patch.object(web, '_mail_diagnostics', return_value={'ok': True})
        self.mail.start()
        self.client = web.app.test_client()

    def tearDown(self):
        self.mail.stop()
        self.hash.stop()
        self.admin.stop()
        self.env.stop()

    def test_main_session_does_not_authorize_admin(self):
        self.assertEqual(self.client.get('/api/admin/pending').status_code, 401)

    def test_proxy_key_authorizes_read(self):
        self.assertEqual(self.client.get('/api/admin/pending', headers={'X-Admin-Key': self.key}).status_code, 200)

    def test_json_key_cannot_replace_proxy_header(self):
        response = self.client.post('/api/admin/mail-test', json={'key': self.key}, headers={'X-Admin-Request': '1'})
        self.assertEqual(response.status_code, 401)

    def test_write_requires_custom_header(self):
        response = self.client.post('/api/admin/mail-test', headers={'X-Admin-Key': self.key})
        self.assertEqual(response.status_code, 403)

    def test_valid_write_is_dispatched(self):
        with patch.object(web, '_mail_diagnostics', return_value={'ok': True}):
            response = self.client.post('/api/admin/mail-test', headers={'X-Admin-Key': self.key, 'X-Admin-Request': '1'})
            self.assertEqual(response.status_code, 200)

    def test_proxy_key_cannot_be_changed_in_browser(self):
        with patch.object(web, '_set_admin_key_hash') as save:
            response = self.client.post('/api/admin/set-key', json={'key': 'replacement-test-key'}, headers={'X-Admin-Key': self.key, 'X-Admin-Request': '1'})
            self.assertEqual(response.status_code, 409)
            save.assert_not_called()

    def test_proxy_panel_does_not_require_key_input(self):
        html = self.client.get('/admin/approvals').get_data(as_text=True)
        self.assertIn('data-admin-proxy="true"', html)

    def test_local_mode_retains_existing_admin_login(self):
        with patch.dict(os.environ, {'ADMIN_PROXY_AUTH': '0'}):
            self.assertEqual(self.client.get('/api/admin/pending').status_code, 200)


if __name__ == '__main__': unittest.main()
