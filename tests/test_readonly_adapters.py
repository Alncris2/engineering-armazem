import json
import unittest
from unittest.mock import patch

from adapters.grafana.query import query_range
from adapters.oracle.select import validate_sql


class ReadOnlyAdaptersTest(unittest.TestCase):
    def test_oracle_rejects_writes_and_multiple_statements(self):
        self.assertEqual("SELECT 1 FROM dual", validate_sql("SELECT 1 FROM dual"))
        for sql in ("DELETE FROM users", "WITH x AS (SELECT 1 FROM dual) DELETE FROM users", "SELECT 1; DELETE FROM users"):
            with self.subTest(sql=sql), self.assertRaises(ValueError):
                validate_sql(sql)

    def test_loki_request_is_get_and_bounded(self):
        class Response:
            def __enter__(self): return self
            def __exit__(self, *args): return False
            def read(self): return b'{"status":"success","data":{"result":[]}}'

        with patch("urllib.request.urlopen", return_value=Response()) as opened:
            result = query_range("https://grafana.example", "private-token", '{app="webagil"}', "1", "2", 3)
        request = opened.call_args.args[0]
        self.assertEqual("GET", request.get_method())
        self.assertIn("limit=100", request.full_url)
        self.assertEqual("success", result["status"])
        self.assertEqual("Bearer private-token", request.get_header("Authorization"))
        with patch("urllib.request.urlopen", return_value=Response()) as proxy_opened:
            query_range("https://grafana.example", None, "{}", "1", "2", datasource_uid="loki-main")
        self.assertIn("/api/datasources/proxy/uid/loki-main/loki/api/v1/query_range", proxy_opened.call_args.args[0].full_url)
        with self.assertRaises(ValueError):
            query_range("http://not-loopback.example", None, "{}", "1", "2")


if __name__ == "__main__":
    unittest.main()
