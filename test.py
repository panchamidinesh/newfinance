import unittest
import os
import sqlite3
import uuid
from app import app, get_db_connection
import pandas as pd


class FlaskAppTestCase(unittest.TestCase):
    def setUp(self):
        self.db_path = 'test.db'
        app.config['DATABASE'] = self.db_path
        app.config['TESTING'] = True
        self.app = app.test_client()
        self.client = self.app
        self.init_test_db()

    def init_test_db(self):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('DROP TABLE IF EXISTS users')
        cursor.execute('DROP TABLE IF EXISTS transactions')
        cursor.execute('''CREATE TABLE users (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            username TEXT NOT NULL UNIQUE,
                            password TEXT NOT NULL)''')
        cursor.execute('''CREATE TABLE transactions (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            username TEXT NOT NULL,
                            type TEXT NOT NULL,
                            category TEXT NOT NULL,
                            amount REAL NOT NULL,
                            note TEXT,
                            date TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
        conn.commit()
        conn.close()
        
        
        def tearDown(self):
             if os.path.exists(self.db_path):
              os.remove(self.db_path)


    def register(self, username, password):
        return self.client.post('/register', data=dict(
            username=username,
            password=password
        ), follow_redirects=True)

    def login(self, username, password):
        return self.client.post('/login', data=dict(
            username=username,
            password=password
        ), follow_redirects=True)

    def test_register_login_logout(self):
        unique_username = f"user_{uuid.uuid4().hex[:6]}"
        response = self.client.post('/register', data={
            'username': unique_username,
            'password': 'testpass'
        }, follow_redirects=True)
        self.assertIn(b'Registered successfully', response.data)

    def test_login_invalid_credentials(self):
        response = self.login('wronguser', 'wrongpass')
        self.assertIn(b'Invalid credentials', response.data)

    def test_dashboard_requires_login(self):
        response = self.client.get('/dashboard', follow_redirects=True)
        self.assertIn(b'You must be logged in', response.data)

    def test_logout(self):
        unique_username = f"user_{uuid.uuid4().hex[:6]}"
        self.client.post('/register', data={
            'username': unique_username,
            'password': 'testpass'
        }, follow_redirects=True)
        self.login(unique_username, 'testpass')

        with self.client:
            response = self.client.get('/dashboard', follow_redirects=True)
            self.assertIn(b'Welcome', response.data)  # Assumes dashboard has a welcome message

        response = self.client.get('/logout', follow_redirects=True)
        with self.client:
            response = self.client.get('/dashboard', follow_redirects=True)
            self.assertIn(b'You must be logged in', response.data)

        with self.client:
            response = self.client.get('/logout', follow_redirects=True)
            self.assertIn(b'You have been logged out.', response.data)

    

    def test_download_csv_report(self):
        unique_username = f"user_{uuid.uuid4().hex[:6]}"
        self.register(unique_username, 'testpass')
        self.login(unique_username, 'testpass')

        self.client.post('/dashboard', data={
            'type': 'income',
            'category': 'Test',
            'amount': '100.00',
            'note': 'CSV test'
        }, follow_redirects=True)

        response = self.client.get('/download_report/csv')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers['Content-Type'], 'text/csv')
        self.assertIn(b'Type,Category,Amount,Note,Date', response.data)

    def test_download_pdf_report(self):
        unique_username = f"user_{uuid.uuid4().hex[:6]}"
        self.register(unique_username, 'testpass')
        self.login(unique_username, 'testpass')

        self.client.post('/dashboard', data={
            'type': 'expense',
            'category': 'Test',
            'amount': '50.00',
            'note': 'PDF test'
        }, follow_redirects=True)

        response = self.client.get('/download_report/pdf')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers['Content-Type'], 'application/pdf')
        self.assertTrue(len(response.data) > 100)  # Ensure some content in PDF


if __name__ == '__main__':
    unittest.main()
