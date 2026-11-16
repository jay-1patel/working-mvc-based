import base64
import unittest

from core.send2_auth import decode_send2_username


class Send2UsernameTests(unittest.TestCase):
    def test_decodes_send2_base64_username(self):
        self.assertEqual(decode_send2_username("Y2FtcGFpZ24="), "campaign")

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
