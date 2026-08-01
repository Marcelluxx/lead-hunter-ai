import socket
import unittest

from src.security.url_policy import SafeUrlPolicy, UrlPolicyError


def resolver_for(*addresses):
    def resolve(host, port, **kwargs):
        family = socket.AF_INET6 if ":" in addresses[0] else socket.AF_INET
        return [(family, socket.SOCK_STREAM, 6, "", (address, port)) for address in addresses]

    return resolve


class SafeUrlPolicyTests(unittest.TestCase):
    def test_accepts_and_normalizes_public_https_url(self):
        policy = SafeUrlPolicy(resolver=resolver_for("93.184.216.34"))

        decision = policy.validate("HTTPS://Example.COM./contact?from=test#fragment")

        self.assertEqual(decision.normalized_url, "https://example.com/contact?from=test")
        self.assertEqual(decision.hostname, "example.com")

    def test_blocks_private_loopback_link_local_and_reserved_targets(self):
        blocked = [
            "http://127.0.0.1/",
            "http://10.0.0.1/",
            "http://169.254.169.254/latest/meta-data/",
            "http://[::1]/",
            "http://[fe80::1]/",
            "http://[::ffff:127.0.0.1]/",
            "http://192.0.2.1/",
        ]

        for url in blocked:
            with self.subTest(url=url), self.assertRaises(UrlPolicyError) as raised:
                SafeUrlPolicy().validate(url)
            self.assertEqual(raised.exception.code, "non_public_ip")

    def test_blocks_private_address_if_dns_returns_mixed_results(self):
        policy = SafeUrlPolicy(resolver=resolver_for("93.184.216.34", "10.0.0.2"))

        with self.assertRaises(UrlPolicyError) as raised:
            policy.validate("https://example.com")

        self.assertEqual(raised.exception.code, "non_public_ip")

    def test_blocks_non_http_schemes_credentials_and_nonstandard_ports(self):
        cases = [
            ("file:///etc/passwd", "invalid_scheme"),
            ("ftp://example.com/file", "invalid_scheme"),
            ("http://user:pass@example.com", "credentials_forbidden"),
            ("https://example.com:8443", "port_forbidden"),
            ("http://localhost", "local_hostname"),
        ]

        for url, expected_code in cases:
            with self.subTest(url=url), self.assertRaises(UrlPolicyError) as raised:
                SafeUrlPolicy(resolver=resolver_for("93.184.216.34")).validate(url)
            self.assertEqual(raised.exception.code, expected_code)

    def test_blocks_dns_rebinding_within_same_crawl_session(self):
        answers = iter(
            [
                resolver_for("93.184.216.34")("example.com", 443),
                resolver_for("93.184.216.35")("example.com", 443),
            ]
        )
        policy = SafeUrlPolicy(resolver=lambda *args, **kwargs: next(answers))
        policy.validate("https://example.com")

        with self.assertRaises(UrlPolicyError) as raised:
            policy.validate("https://example.com/about")

        self.assertEqual(raised.exception.code, "dns_rebinding")

    def test_restricts_discovered_links_to_explicit_hosts(self):
        policy = SafeUrlPolicy(resolver=resolver_for("93.184.216.34"))

        with self.assertRaises(UrlPolicyError) as raised:
            policy.validate("https://cdn.example.net/file", allowed_hosts={"example.com"})

        self.assertEqual(raised.exception.code, "host_forbidden")


if __name__ == "__main__":
    unittest.main()
