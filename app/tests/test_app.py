"""Offline boundary tests; these never connect to a database."""
import unittest
import base64
from unittest.mock import patch, MagicMock
from app import app, parse_date, number
from services import UserError, book, cancel
from db import connect, ConfigurationError

class WebTests(unittest.TestCase):
    def setUp(self):
        app.config['TESTING'] = True
        self.client = app.test_client()
        self.auth = patch('auth.current_user_id', return_value='user_demo')
        self.auth.start()
        self.addCleanup(self.auth.stop)
        self.app_auth = patch('app.current_user_id', return_value='user_demo')
        self.app_auth.start()
        self.addCleanup(self.app_auth.stop)
        publishable = 'pk_test_' + base64.b64encode(b'railway-test.clerk.accounts.dev$').decode()
        self.keys = patch.dict('os.environ', {'CLERK_SECRET_KEY':'sk_test_dummy',
                                            'CLERK_PUBLISHABLE_KEY':publishable, 'CLERK_KEY':''})
        self.keys.start()
        self.addCleanup(self.keys.stop)

    def test_missing_database_friendly(self):
        with patch.dict('os.environ', {'DATABASE_URL':''}):
            response = self.client.get('/')
            self.assertEqual(response.status_code,503)
            self.assertIn(b'Set DATABASE_URL',response.data)

    def test_lookup_and_csrf(self):
        self.assertEqual(self.client.get('/booking').status_code,200)
        self.assertEqual(self.client.post('/cancel',data={'pnr':'ABC'}).status_code,400)
        self.assertEqual(self.client.get('/booking?pnr=bad').status_code,400)

    def test_validation(self):
        for value in ('-1','bad','0'):
            with self.assertRaises(UserError): number(value)
        with self.assertRaises(UserError): parse_date('2026-02-30')

    def test_templates_empty_states(self):
        with patch('app.rows',return_value=[]):
            response=self.client.get('/')
            self.assertIn(b'No stations yet',response.data)
        with patch('app.connect') as factory:
            conn=factory.return_value.__enter__.return_value
            conn.execute.return_value.fetchall.return_value=[]
            self.assertEqual(self.client.get('/schedule').status_code,200)

    def test_ssl_overrides_insecure_url(self):
        with patch.dict('os.environ',{'DATABASE_URL':'postgresql://example.invalid/demo?sslmode=disable'}), patch('db.psycopg.connect') as factory:
            connect()
            self.assertEqual(factory.call_args.kwargs['sslmode'],'require')

class TransactionTests(unittest.TestCase):
    def test_contested_seat_aborts_before_passenger_insert(self):
        with patch('services.connect') as factory:
            conn=factory.return_value.__enter__.return_value
            conn.execute.return_value.fetchone.side_effect=[{'seat_id':1},{'booking_id':2}]
            with self.assertRaises(UserError): book(1,'Demo','demo@example.test','user_demo')
            self.assertEqual(conn.execute.call_count,2)
            self.assertIn('FOR UPDATE',conn.execute.call_args_list[0].args[0])
            self.assertIs(factory.return_value.__exit__.call_args.args[0], UserError)

    def test_successful_booking_transaction(self):
        with patch('services.connect') as factory:
            conn=factory.return_value.__enter__.return_value
            conn.execute.return_value.fetchone.side_effect=[{'seat_id':1},None,{'passenger_id':2,'full_name':'Demo'}]
            pnr=book(1,'Demo','demo@example.test','user_demo')
            self.assertRegex(pnr,r'^[A-Z0-9]{10}$')
            self.assertEqual(conn.execute.call_count,4)
            self.assertEqual(factory.return_value.__exit__.call_args.args,(None,None,None))

    def test_cancel_already_cancelled(self):
        with patch('services.connect') as factory:
            conn=factory.return_value.__enter__.return_value
            conn.execute.return_value.fetchone.side_effect=[{'seat_id':1},None]
            with self.assertRaisesRegex(UserError,'already cancelled'): cancel('ABCDEFGHIJ','user_demo')

if __name__ == '__main__': unittest.main()
