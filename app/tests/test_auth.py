"""Real SDK/JWT verification with synthetic RSA keys; no Clerk/Neon network calls."""
import base64
import time
import unittest
from types import SimpleNamespace
from unittest.mock import patch

import jwt
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization

from app import app
from auth import current_user_id, safe_next
from services import booking, cancel, UserError

DOMAIN = 'railway-test.clerk.accounts.dev'
KEY = 'pk_test_' + base64.b64encode((DOMAIN + '$').encode()).decode()


class AuthTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        cls.public_key = cls.private_key.public_key().public_bytes(
            serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo).decode()

    def setUp(self):
        self.env = patch.dict('os.environ', {
            'CLERK_PUBLISHABLE_KEY':KEY, 'CLERK_SECRET_KEY':'sk_test_synthetic',
            'CLERK_AUTHORIZED_PARTIES':'http://localhost:5000', 'CLERK_KEY':'demo-clerk-key'})
        self.env.start()
        self.addCleanup(self.env.stop)
        self.remote = patch('clerk_backend_api.security.verifytoken._get_remote_jwt_key', return_value=self.public_key)
        self.remote.start()
        self.addCleanup(self.remote.stop)
        app.config['TESTING'] = True
        self.client = app.test_client()

    def token(self, **changes):
        now = int(time.time())
        payload = dict(sub='user_demo', sid='sess_demo', exp=now+60, iat=now-1, nbf=now-1,
                       iss='https://' + DOMAIN, azp='http://localhost:5000')
        payload.update(changes)
        return jwt.encode(payload, self.private_key, algorithm='RS256', headers={'kid':'test'})

    def test_real_sdk_validates_cookie(self):
        with app.test_request_context('/', headers={'Cookie':'__session=' + self.token()}):
            self.assertEqual(current_user_id(),'user_demo')

    def test_expiry_origin_issuer_and_signature_rejected(self):
        for changes in ({'exp':int(time.time())-100}, {'azp':'https://attacker.invalid'}, {'iss':'https://other.clerk.accounts.dev'}):
            with self.subTest(changes=changes), app.test_request_context('/', headers={'Authorization':'Bearer ' + self.token(**changes)}):
                self.assertIsNone(current_user_id())
        forged = jwt.encode({'sub':'user_demo','exp':int(time.time())+60}, 'synthetic-invalid-signing-key-1234567890', algorithm='HS256')
        with app.test_request_context('/',headers={'Authorization':'Bearer '+forged}):
            self.assertIsNone(current_user_id())

    def test_protected_pages_redirect_before_database(self):
        with patch('app.connect') as conn, patch('app.rows') as rows:
            for path in ('/booking','/schedule'):
                response=self.client.get(path)
                self.assertEqual(response.status_code,302)
                self.assertIn('/sign-in',response.location)
            conn.assert_not_called()
            rows.assert_not_called()

    def test_auth_controls_and_safe_redirect(self):
        response=self.client.get('/sign-in?next=https://attacker.invalid')
        self.assertEqual(response.status_code,200)
        self.assertIn(b'data-next="/"',response.data)
        self.assertIn(b'clerk-js@6',response.data)
        self.assertNotIn(b'sk_test_synthetic',response.data)
        for value in ('//attacker.invalid','/\\attacker.invalid','/sign-in','https://attacker.invalid'):
            self.assertEqual(safe_next(value),'/')

    def test_anonymous_post_cannot_book(self):
        with self.client.session_transaction() as session:
            session['csrf']='test-csrf'
        with patch('app.book') as reserve:
            response=self.client.post('/book',data={'csrf':'test-csrf'})
            self.assertEqual(response.status_code,401)
            reserve.assert_not_called()

    def test_clerk_key_still_required_and_scoped_to_account(self):
        with patch('auth.current_user_id', return_value='user_new'), patch('app.current_user_id',return_value='user_new'):
            with self.client.session_transaction() as session:
                session['schedule_clerk_user']='user_other'
            with patch('app.connect') as conn:
                response=self.client.get('/schedule')
                self.assertIn(b'Classroom clerk key',response.data)
                conn.assert_not_called()

    def test_lookup_filters_owner_in_sql(self):
        with patch('services.rows',return_value=[]) as query:
            with self.assertRaises(UserError): booking('ABCDEFGHIJ','user_other')
            self.assertEqual(query.call_args.args[1],('ABCDEFGHIJ','user_other'))
            self.assertIn('b.clerk_user_id=%s',query.call_args.args[0])

    def test_other_owner_cannot_cancel(self):
        with patch('services.connect') as factory:
            conn=factory.return_value.__enter__.return_value
            conn.execute.return_value.fetchone.return_value=None
            with self.assertRaises(UserError): cancel('ABCDEFGHIJ','user_other')
            self.assertEqual(conn.execute.call_count,1)
            self.assertEqual(conn.execute.call_args.args[1],('ABCDEFGHIJ','user_other'))


if __name__ == '__main__': unittest.main()
