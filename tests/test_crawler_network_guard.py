import unittest

from src.crawler import HybridCrawler
from src.security import SafeUrlPolicy


class FakeRequest:
    def __init__(self, url, redirected_from=None):
        self.url = url
        self.redirected_from = redirected_from


class FakeRoute:
    def __init__(self, request):
        self.request = request
        self.aborted_with = None
        self.continued = False

    async def abort(self, reason):
        self.aborted_with = reason

    async def continue_(self):
        self.continued = True


class CrawlerNetworkGuardTests(unittest.IsolatedAsyncioTestCase):
    async def test_browser_route_blocks_private_subresource(self):
        crawler = HybridCrawler(url_policy=SafeUrlPolicy())
        route = FakeRoute(FakeRequest("http://169.254.169.254/latest/meta-data/"))

        await crawler._secure_route(route)

        self.assertEqual(route.aborted_with, "blockedbyclient")
        self.assertFalse(route.continued)
        self.assertIn("non_public_ip", crawler._blocked_requests)

    async def test_browser_route_allows_public_request(self):
        crawler = HybridCrawler(url_policy=SafeUrlPolicy())
        route = FakeRoute(FakeRequest("https://93.184.216.34/asset.js"))

        await crawler._secure_route(route)

        self.assertTrue(route.continued)
        self.assertIsNone(route.aborted_with)

    async def test_browser_route_caps_redirect_chain(self):
        previous = None
        for index in range(7):
            previous = FakeRequest(f"https://93.184.216.34/{index}", previous)
        crawler = HybridCrawler(url_policy=SafeUrlPolicy(max_redirects=5))
        route = FakeRoute(previous)

        await crawler._secure_route(route)

        self.assertEqual(route.aborted_with, "blockedbyclient")
        self.assertIn("too_many_redirects", crawler._blocked_requests)


if __name__ == "__main__":
    unittest.main()
