"""Plain usernames must authenticate against Base64 Send2 DB rows only."""

import unittest
from unittest.mock import patch

from core.send2_auth import encode_send2_username
from routes import auth as auth_routes


class PlainUsernameSessionAuthTests(unittest.TestCase):
    def test_admin_from_pair_accepts_plain_username_for_encoded_row(self):
        plain = "test_support_"
        encoded = encode_send2_username(plain)
        session_id = "live-session-abc"

        def fake_get(username):
            if username == encoded:
                return {
                    "username": encoded,
                    "session_id": session_id,
                    "role": "admin",
                    "permissions": {},
                    "tenant_id": "c",
                }
            return None

        with patch.object(auth_routes, "get_admin_by_username", side_effect=fake_get):
            admin = auth_routes._admin_from_pair(plain, session_id)

        self.assertEqual(admin["username"], plain)
        self.assertEqual(admin["tenant_id"], "c")
        self.assertEqual(admin["role"], "admin")

    def test_admin_from_pair_rejects_encoded_username(self):
        plain = "campaign"
        encoded = encode_send2_username(plain)
        session_id = "sess-1"

        with patch.object(
            auth_routes,
            "get_admin_by_username",
            return_value={
                "username": encoded,
                "session_id": session_id,
                "role": "sub_admin",
                "permissions": {},
                "tenant_id": "acme",
            },
        ):
            with self.assertRaises(auth_routes.HTTPException) as ctx:
                auth_routes._admin_from_pair(encoded, session_id)
        self.assertEqual(ctx.exception.status_code, 401)

    def test_admin_target_resolves_plain_path_username(self):
        plain = "cars"
        encoded = encode_send2_username(plain)
        row = {
            "username": encoded,
            "role": "admin",
            "tenant_id": "c",
            "permissions": {},
        }
        with patch.object(auth_routes, "get_admin_by_username", side_effect=lambda u: row if u == encoded else None):
            target = auth_routes._admin_target(plain, {"role": "admin", "tenant_id": "c"})
        self.assertIsNotNone(target)
        self.assertEqual(target["username"], encoded)

    def test_list_admins_returns_plain_usernames(self):
        encoded = encode_send2_username("campaign")
        with patch.object(
            auth_routes,
            "list_admin_records",
            return_value=[
                {
                    "username": encoded,
                    "email": None,
                    "role": "admin",
                    "permissions": {},
                    "created_at": None,
                    "tenant_id": "c",
                }
            ],
        ):
            result = auth_routes.list_admins(current_admin={"role": "super_admin"})
        self.assertEqual(result["admins"][0]["username"], "campaign")

    def test_public_username_helper(self):
        self.assertEqual(auth_routes._public_username("dGVzdF9zdXBwb3J0Xw=="), "test_support_")
        self.assertEqual(auth_routes._public_username("test_support_"), "test_support_")


if __name__ == "__main__":
    unittest.main()
