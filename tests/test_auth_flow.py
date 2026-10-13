"""Login/captcha regression checks against Flask and an isolated user database."""
import os
from pathlib import Path
import sqlite3
import sys
import time
import unittest
from unittest.mock import patch
from werkzeug.security import generate_password_hash

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'web'))
import app as web


class AuthFlowTests(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(':memory:')
        self.conn.row_factory = sqlite3.Row
        self.db = patch.object(web.skills_db, 'get_conn', return_value=self.conn)
        self.db.start()
        self.addCleanup(self.conn.close)
        self.addCleanup(self.db.stop)
        self.captchas = patch.object(web, '_CAPTCHAS', {})
        self.captchas.start()
        self.addCleanup(self.captchas.stop)
        self.rates = patch.object(web, '_RATE', {})
        self.rates.start()
        self.addCleanup(self.rates.stop)
        self.env = patch.dict(os.environ, {'EMAIL_VERIFY': '0', 'ADMIN_USER': '', 'ADMIN_PASS': ''})
        self.env.start()
        self.addCleanup(self.env.stop)
        web.init_users_table()
        self.conn.execute('INSERT INTO users(username,password_hash,status) VALUES(?,?,?)',
                          ('auth_test', generate_password_hash('Test#123456'), 'approved'))
        self.conn.commit()
        self.client = web.app.test_client()

    def challenge(self, verified=True):
        response = self.client.get('/api/captcha/new')
        self.assertEqual(response.status_code, 200)
        cid = response.get_json()['id']
        if verified:
            result = self.client.post('/api/captcha/verify', json={'id': cid, 'x': web._CAPTCHAS[cid]['gap_x']})
            self.assertEqual(result.status_code, 200)
        return cid

    def login(self, cid='', password='Test#123456'):
        return self.client.post('/api/auth/login', json={'username': 'auth_test', 'password': password, 'captcha_id': cid})

    def test_guest_has_no_session_and_private_api_is_blocked(self):
        self.assertIsNone(self.client.get('/api/auth/me').get_json()['user'])
        self.assertEqual(self.client.get('/api/ai/config').status_code, 401)

    def test_missing_and_unverified_captcha_cannot_login(self):
        self.assertEqual(self.login().status_code, 400)
        self.assertEqual(self.login(self.challenge(False)).status_code, 400)

    def test_wrong_drag_then_correct_drag(self):
        cid = self.challenge(False)
        self.assertEqual(self.client.post('/api/captcha/verify', json={'id': cid, 'x': -100}).status_code, 400)
        self.assertFalse(web._CAPTCHAS[cid]['verified'])
        self.assertEqual(self.client.post('/api/captcha/verify', json={'id': cid, 'x': web._CAPTCHAS[cid]['gap_x']}).status_code, 200)
        self.assertEqual(self.login(cid).status_code, 200)

    def test_login_session_logout_and_single_use(self):
        cid = self.challenge()
        self.assertEqual(self.login(cid).status_code, 200)
        self.assertEqual(self.client.get('/api/auth/me').get_json()['user']['username'], 'auth_test')
        self.assertEqual(self.login(cid).status_code, 400)
        self.assertEqual(self.client.post('/api/auth/logout').status_code, 200)
        self.assertIsNone(self.client.get('/api/auth/me').get_json()['user'])

    def test_wrong_password_can_retry_without_getting_stuck(self):
        cid = self.challenge()
        self.assertEqual(self.login(cid, 'incorrect').status_code, 401)
        self.assertFalse(web._CAPTCHAS[cid]['used'])
        self.assertEqual(self.login(cid).status_code, 200)

    def test_pending_and_rejected_accounts_do_not_create_session(self):
        for status in ('pending', 'rejected'):
            with self.subTest(status=status):
                self.conn.execute('UPDATE users SET status=?', (status,))
                self.conn.commit()
                result = self.login(self.challenge())
                self.assertEqual(result.status_code, 403)
                self.assertEqual(result.get_json()['code'], status)
                self.assertIsNone(self.client.get('/api/auth/me').get_json()['user'])

    def test_expired_and_exhausted_captcha(self):
        cid = self.challenge()
        web._CAPTCHAS[cid]['expires'] = time.time() - 1
        self.assertEqual(self.login(cid).status_code, 400)
        cid = self.challenge(False)
        for _ in range(6):
            self.assertEqual(self.client.post('/api/captcha/verify', json={'id': cid, 'x': -100}).status_code, 400)
        self.assertNotIn(cid, web._CAPTCHAS)

    def test_registration_waits_for_approval_and_consumes_captcha(self):
        cid = self.challenge()
        result = self.client.post('/api/auth/register', json={'username': 'new_user', 'password': 'Test#123456', 'captcha_id': cid})
        self.assertEqual(result.status_code, 200, result.get_json())
        self.assertEqual(result.get_json()['status'], 'pending')
        self.assertTrue(web._CAPTCHAS[cid]['used'])
        self.assertIsNone(self.client.get('/api/auth/me').get_json()['user'])


if __name__ == '__main__':
    unittest.main()
