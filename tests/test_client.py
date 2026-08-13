import json
import unittest
from urllib.error import HTTPError

from ingestion.client import NHLHTTPClient, NHLAPIError


class Response:
    status = 200
    headers = {"Content-Type": "application/json"}

    def __init__(self, value):
        self.value = value

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def read(self):
        return json.dumps(self.value).encode()


class ClientTests(unittest.TestCase):
    def test_query_encoding_and_metadata(self):
        seen = []

        def opener(request, timeout):
            seen.append((request.full_url, timeout, request.headers))
            return Response({"data": [], "total": 0})

        client = NHLHTTPClient(base_url="https://example.test/stats/", opener=opener, sleep=lambda _: None)
        payload, metadata = client.get_json("skater/summary", {"sort": [{"property": "playerId", "direction": "ASC"}], "limit": 100})
        self.assertEqual(payload["total"], 0)
        self.assertEqual(metadata.status, 200)
        self.assertIn("sort=%5B%7B%22direction%22%3A%22ASC%22%2C%22property%22%3A%22playerId%22%7D%5D", seen[0][0])

    def test_cache_hooks_and_non_json(self):
        stored = {}
        calls = []

        def opener(request, timeout):
            calls.append(request.full_url)
            return Response({"data": [1]})

        def put(key, body, metadata):
            stored[key] = (body, metadata)

        client = NHLHTTPClient(opener=opener, cache_get=stored.get, cache_put=put, sleep=lambda _: None)
        client.get_json("x")
        _, metadata = client.get_json("x")
        self.assertEqual(len(calls), 1)
        self.assertTrue(metadata.from_cache)

    def test_retries_rate_limit_then_succeeds(self):
        attempts = []

        def opener(request, timeout):
            attempts.append(request.full_url)
            if len(attempts) == 1:
                raise HTTPError(request.full_url, 429, "rate limited", {"Retry-After": "0"}, None)
            return Response({"ok": True})

        client = NHLHTTPClient(opener=opener, retries=1, sleep=lambda _: None)
        payload, metadata = client.get_json("x")
        self.assertTrue(payload["ok"])
        self.assertEqual(metadata.attempts, 2)


if __name__ == "__main__":
    unittest.main()
