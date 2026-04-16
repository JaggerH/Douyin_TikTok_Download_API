"""Active cookie refresh from CookieCloud on auth failure.

Usage::

    from crawlers.utils.cookie_refresher import get_refresher

    refresher = get_refresher()
    if refresher.available:
        ok = await refresher.refresh("bilibili", bilibili_crawler_instance)

Requires env vars:
    COOKIECLOUD_URL      — CookieCloud server base URL
    COOKIECLOUD_UUID     — CookieCloud user UUID
    COOKIECLOUD_PASSWORD — CookieCloud user password
"""
from __future__ import annotations

import hashlib
import json
import os
from base64 import b64decode

import httpx
from Cryptodome.Cipher import AES

from crawlers.utils.logger import logger

# Domain to fetch from CookieCloud per platform
_DOMAIN_MAP: dict[str, str] = {
    "bilibili": "bilibili.com",
    "douyin": "douyin.com",
    "tiktok": "tiktok.com",
    "youtube": "youtube.com",
}


def _evp_bytes_to_key(passphrase: bytes, salt: bytes, key_len: int = 32, iv_len: int = 16):
    """OpenSSL EVP_BytesToKey (MD5-based), used by CookieCloud / CryptoJS AES."""
    d = b""
    d_i = b""
    while len(d) < key_len + iv_len:
        d_i = hashlib.md5(d_i + passphrase + salt).digest()
        d += d_i
    return d[:key_len], d[key_len: key_len + iv_len]


def _decrypt_cookiecloud(encrypted: str, uuid: str, password: str) -> dict:
    raw = b64decode(encrypted)
    if raw[:8] != b"Salted__":
        raise RuntimeError("Invalid CookieCloud format (missing Salted__ header)")
    salt = raw[8:16]
    cipher_bytes = raw[16:]
    passphrase = hashlib.md5(f"{uuid}-{password}".encode()).hexdigest()[:16].encode()
    key, iv = _evp_bytes_to_key(passphrase, salt)
    cipher = AES.new(key, AES.MODE_CBC, iv)
    decrypted = cipher.decrypt(cipher_bytes)
    decrypted = decrypted[: -decrypted[-1]]  # PKCS7 unpad
    return json.loads(decrypted.decode("utf-8"))


class CookieRefresher:
    """Fetches fresh cookies from CookieCloud and pushes them to crawlers.

    Instantiate once as a singleton via ``get_refresher()``.
    If the required env vars are absent the instance is inert (``available=False``)
    and all refresh calls return False without raising.
    """

    def __init__(self):
        self._url = os.environ.get("COOKIECLOUD_URL", "").rstrip("/")
        self._uuid = os.environ.get("COOKIECLOUD_UUID", "")
        self._password = os.environ.get("COOKIECLOUD_PASSWORD", "")
        self._available = bool(self._url and self._uuid and self._password)
        if not self._available:
            logger.warning(
                "CookieRefresher: COOKIECLOUD_URL/UUID/PASSWORD not configured — "
                "active cookie refresh is disabled"
            )

    @property
    def available(self) -> bool:
        return self._available

    def fetch_domain_cookies(self, domain: str) -> dict[str, str]:
        """Pull and decrypt cookies for *domain* from CookieCloud.

        Returns a ``{name: value}`` dict.  Raises on network or decrypt errors.
        """
        resp = httpx.get(f"{self._url}/get/{self._uuid}", timeout=15)
        resp.raise_for_status()
        data = resp.json()
        encrypted = data.get("encrypted", "")
        if not encrypted:
            raise RuntimeError("CookieCloud returned empty encrypted data")

        all_data = _decrypt_cookiecloud(encrypted, self._uuid, self._password)
        cookie_data = all_data.get("cookie_data", all_data)

        cookies: dict[str, str] = {}
        for d, cookie_list in cookie_data.items():
            if isinstance(cookie_list, list) and domain in d:
                for c in cookie_list:
                    if isinstance(c, dict) and "name" in c:
                        cookies[c["name"]] = c["value"]

        if not cookies:
            raise RuntimeError(f"No cookies found for domain '{domain}' in CookieCloud")

        return cookies

    async def refresh(self, platform: str, crawler) -> bool:
        """Fetch fresh cookies for *platform* and call ``crawler.update_cookie()``.

        Args:
            platform: One of ``bilibili``, ``youtube``, ``douyin``, ``tiktok``.
            crawler:  The crawler instance — must have an ``update_cookie(str)`` coroutine.

        Returns:
            ``True`` on success, ``False`` on any failure (logged but not re-raised).
        """
        if not self._available:
            return False

        domain = _DOMAIN_MAP.get(platform)
        if not domain:
            logger.warning(f"CookieRefresher.refresh: unknown platform '{platform}'")
            return False

        try:
            cookies = self.fetch_domain_cookies(domain)
            cookie_str = "; ".join(f"{k}={v}" for k, v in cookies.items())
            await crawler.update_cookie(cookie_str)
            logger.info(
                f"CookieRefresher: {platform} cookies refreshed "
                f"({len(cookies)} keys from CookieCloud)"
            )
            return True
        except Exception as exc:
            logger.error(f"CookieRefresher: failed to refresh {platform}: {exc}")
            return False


_instance: CookieRefresher | None = None


def get_refresher() -> CookieRefresher:
    """Return the process-wide CookieRefresher singleton."""
    global _instance
    if _instance is None:
        _instance = CookieRefresher()
    return _instance
