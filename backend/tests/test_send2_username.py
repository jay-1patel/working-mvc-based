import base64
import unittest

from core.send2_auth import (
    admin_username_candidates,
    decode_send2_username,
    encode_send2_username,
    is_encoded_send2_username,
    normalize_login_username,
)


class Send2UsernameTests(unittest.TestCase):
    def test_decodes_send2_base64_username(self):
        self.assertEqual(decode_send2_username("Y2FtcGFpZ24="), "campaign")

    def test_encodes_plain_username(self):
        self.assertEqual(encode_send2_username("test_support_"), "dGVzdF9zdXBwb3J0Xw==")
        self.assertEqual(encode_send2_username("campaign"), "Y2FtcGFpZ24=")

    def test_normalize_accepts_plain_only(self):
        self.assertEqual(normalize_login_username("test_support_"), "test_support_")
        with self.assertRaises(ValueError):
            normalize_login_username("dGVzdF9zdXBwb3J0Xw==")

    def test_is_encoded_detects_canonical_base64(self):
        self.assertTrue(is_encoded_send2_username("dGVzdF9zdXBwb3J0Xw=="))
        self.assertFalse(is_encoded_send2_username("test_support_"))

    def test_candidates_encoded_only(self):
        self.assertEqual(
            admin_username_candidates("test_support_"),
            ["dGVzdF9zdXBwb3J0Xw=="],
        )
        with self.assertRaises(ValueError):
            admin_username_candidates("dGVzdF9zdXBwb3J0Xw==")

    def test_accepts_surrounding_transport_whitespace(self):
        self.assertEqual(decode_send2_username("  Y2FtcGFpZ24=  "), "campaign")

    def test_rejects_plain_or_malformed_username(self):
        for value in ("campaign", "not-base64!", "", "===="):
            with self.subTest(value=value), self.assertRaises(ValueError):
                decode_send2_username(value)

    def test_rejects_non_utf8_payload(self):
        encoded = base64.b64encode(b"\xff\xfe").decode("ascii")
        with self.assertRaises(ValueError):
            decode_send2_username(encoded)


if __name__ == "__main__":
    unittest.main()
