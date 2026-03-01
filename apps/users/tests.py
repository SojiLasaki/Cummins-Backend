from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase
from rest_framework.test import APIClient


class AuthLoginApiTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        user_model = get_user_model()
        self.user = user_model.objects.create_user(
            username="auth_login_user",
            email="auth_login_user@example.com",
            password="auth-login-pass-123",
            role="admin",
        )

    def test_login_returns_tokens(self):
        response = self.client.post(
            "/api/auth/login/",
            {"username": "auth_login_user", "password": "auth-login-pass-123"},
            format="json",
            HTTP_HOST="localhost",
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("access", response.data)
        self.assertIn("refresh", response.data)
        self.assertEqual(response.data.get("username"), "auth_login_user")
        self.assertEqual(response.data.get("role"), "admin")

    def test_login_rejects_invalid_password(self):
        response = self.client.post(
            "/api/auth/login/",
            {"username": "auth_login_user", "password": "wrong-pass"},
            format="json",
            HTTP_HOST="localhost",
        )
        self.assertEqual(response.status_code, 401)

    def test_login_without_trailing_slash_returns_tokens(self):
        response = self.client.post(
            "/api/auth/login",
            {"username": "auth_login_user", "password": "auth-login-pass-123"},
            format="json",
            HTTP_HOST="localhost",
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("access", response.data)
        self.assertIn("refresh", response.data)


class SeedDemoUsersCommandTests(TestCase):
    def setUp(self):
        self.client = APIClient()

    def test_seed_demo_users_creates_loginable_accounts(self):
        call_command("seed_demo_users")

        credentials = [
            ("admin", "admin", "admin"),
            ("office", "office", "office"),
            ("engine", "engine", "technician"),
            ("electrical", "electrical", "technician"),
            ("customer", "customer", "customer"),
            ("login_probe", "login_probe", "admin"),
        ]

        for username, password, role in credentials:
            response = self.client.post(
                "/api/auth/login/",
                {"username": username, "password": password},
                format="json",
                HTTP_HOST="localhost",
            )
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.data.get("username"), username)
            self.assertEqual(response.data.get("role"), role)
