import importlib.util
import unittest
from pathlib import Path


spec = importlib.util.spec_from_file_location("nextcloud_client", Path(__file__).parents[1] / "nextcloud_client.py")
client = importlib.util.module_from_spec(spec)
spec.loader.exec_module(client)


class ClientTests(unittest.TestCase):
    def test_http_and_https_urls_are_supported(self):
        self.assertEqual(client.normalize_url("http://cloud.local/index.php/apps/notes"), "http://cloud.local")
        self.assertEqual(client.normalize_url("https://cloud.example.com/"), "https://cloud.example.com")

    def test_copied_login_url_is_normalized(self):
        self.assertEqual(client.normalize_url("http://cloud.local/index.php/login?foo=bar"), "http://cloud.local")


if __name__ == "__main__":
    unittest.main()
