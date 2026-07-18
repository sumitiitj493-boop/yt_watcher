import asyncio
import ipaddress
import os
import socket
from functools import lru_cache
from urllib.parse import urlparse

UNSAFE_HOSTNAMES = {
    "localhost",
    "localhost.localdomain",
    "ip6-localhost",
    "ip6-loopback",
}

TRUSTED_PUBLIC_MEDIA_HOSTS = {
    "youtube.com",
    "youtu.be",
    "googlevideo.com",
    "ytimg.com",
    "instagram.com",
    "cdninstagram.com",
    "facebook.com",
    "fbcdn.net",
    "tiktok.com",
    "tiktokcdn.com",
    "twitter.com",
    "x.com",
    "twimg.com",
    "vimeo.com",
    "vimeocdn.com",
    "dailymotion.com",
    "dmcdn.net",
    "twitch.tv",
    "soundcloud.com",
    "reddit.com",
}

BLOCKED_PORTS = {
    0,
    22,      # SSH
    23,      # Telnet
    25,      # SMTP
    53,      # DNS
    110,     # POP3
    143,     # IMAP
    3306,    # MySQL
    5432,    # Postgres
    6379,    # Redis
    8000,    # common internal dev API
    8080,    # common internal web app
    9200,    # Elasticsearch
    11211,   # Memcached
    27017,   # MongoDB
}


def _private_urls_allowed() -> bool:
    return os.environ.get("APP_ALLOW_PRIVATE_URLS", "").strip().lower() in {"1", "true", "yes", "on"}


def _strict_dns_guard_enabled() -> bool:
    return os.environ.get("APP_STRICT_URL_DNS_GUARD", "").strip().lower() in {"1", "true", "yes", "on"}


def _is_unsafe_ip(ip: ipaddress._BaseAddress) -> bool:
    return any([
        ip.is_private,
        ip.is_loopback,
        ip.is_link_local,
        ip.is_multicast,
        ip.is_reserved,
        ip.is_unspecified,
    ])


def _strip_trailing_dot(hostname: str) -> str:
    return hostname.strip().strip(".").lower()


def _is_trusted_public_media_host(hostname: str) -> bool:
    return any(hostname == domain or hostname.endswith(f".{domain}") for domain in TRUSTED_PUBLIC_MEDIA_HOSTS)


@lru_cache(maxsize=2048)
def _resolve_host(hostname: str) -> tuple[str, ...]:
    infos = socket.getaddrinfo(hostname, None, type=socket.SOCK_STREAM)
    addresses: list[str] = []
    for info in infos:
        sockaddr = info[4]
        if sockaddr and sockaddr[0] not in addresses:
            addresses.append(sockaddr[0])
    return tuple(addresses)


def validate_public_url_sync(url: str) -> str:
    """Validate that a user-supplied URL is safe for server-side fetching.

    This is an SSRF guard for yt-dlp metadata/download calls. It intentionally
    rejects localhost, private networks, link-local/cloud metadata ranges,
    unsafe schemes, credentials-in-URL, and risky internal service ports.

    DNS-level SSRF checks can false-positive on consumer/VPN/ad-blocking DNS.
    They are skipped for known public media hosts by default. Set
    APP_STRICT_URL_DNS_GUARD=1 to force DNS checks for every hostname.

    Set APP_ALLOW_PRIVATE_URLS=1 only for trusted local development if you need
    to fetch from private network addresses.
    """
    raw_url = str(url or "").strip()
    if not raw_url:
        raise ValueError("URL is required")

    parsed = urlparse(raw_url)
    scheme = parsed.scheme.lower()
    if scheme not in {"http", "https"}:
        raise ValueError("Only http and https URLs are allowed")

    if parsed.username or parsed.password:
        raise ValueError("URLs with embedded credentials are not allowed")

    hostname = parsed.hostname
    if not hostname:
        raise ValueError("URL must include a hostname")

    hostname = _strip_trailing_dot(hostname)
    if hostname in UNSAFE_HOSTNAMES or hostname.endswith(".localhost"):
        raise ValueError("Localhost URLs are not allowed")

    if parsed.port is not None and parsed.port in BLOCKED_PORTS and not _private_urls_allowed():
        raise ValueError(f"Port {parsed.port} is not allowed for public downloads")

    if _private_urls_allowed():
        return raw_url

    try:
        ip = ipaddress.ip_address(hostname)
        if _is_unsafe_ip(ip):
            raise ValueError("Private or internal IP addresses are not allowed")
        return raw_url
    except ValueError as exc:
        if "Private or internal" in str(exc):
            raise
        # Host is not an IP literal; continue with DNS resolution.

    if _is_trusted_public_media_host(hostname) and not _strict_dns_guard_enabled():
        return raw_url

    try:
        addresses = _resolve_host(hostname)
    except socket.gaierror as exc:
        raise ValueError(f"Unable to resolve hostname: {hostname}") from exc

    if not addresses:
        raise ValueError("Hostname did not resolve to any IP address")

    for address in addresses:
        try:
            ip = ipaddress.ip_address(address)
        except ValueError:
            raise ValueError("Hostname resolved to an invalid IP address")
        if _is_unsafe_ip(ip):
            raise ValueError("URL resolves to a private or internal network address")

    return raw_url


async def validate_public_url(url: str) -> str:
    return await asyncio.to_thread(validate_public_url_sync, url)
