"""Tests for proxy module."""
import unittest
import tempfile
import os
from proxy import ProxyManager


class TestProxyManager(unittest.TestCase):
    def setUp(self):
        self.temp_config = tempfile.NamedTemporaryFile(delete=False, suffix=".yaml", mode="w")
        self.temp_config.write("""
mixed-port: 7890
proxies:
  - {name: 'HK 01', type: ss, server: hk.example.com, port: 1234, cipher: aes-128-gcm, password: test}
  - {name: 'JP 01', type: ss, server: jp.example.com, port: 5678, cipher: aes-128-gcm, password: test}
""")
        self.temp_config.close()
        self.pm = ProxyManager(self.temp_config.name)

    def tearDown(self):
        if os.path.exists(self.temp_config.name):
            os.remove(self.temp_config.name)

    def test_loads_nodes(self):
        self.assertEqual(len(self.pm.nodes), 2)

    def test_parses_mixed_port(self):
        self.assertEqual(self.pm.local_port, 7890)

    def test_get_local_proxy(self):
        proxy = self.pm.get_local_proxy()
        self.assertEqual(proxy["http"], "http://127.0.0.1:7890")
        self.assertEqual(proxy["https"], "http://127.0.0.1:7890")

    def test_select_random_returns_node(self):
        node = self.pm.select_random()
        self.assertIsNotNone(node)
        self.assertIn(node.name, ["HK 01", "JP 01"])

    def test_mark_node_failed(self):
        node = self.pm.nodes[0]
        self.pm.mark_node_failed(node)
        self.assertEqual(node.fail_count, 1)


if __name__ == "__main__":
    unittest.main()
