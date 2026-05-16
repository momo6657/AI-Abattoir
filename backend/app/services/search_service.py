from typing import Optional, List, Dict, Any
import ipaddress
import socket
from urllib.parse import urlparse
import httpx
from bs4 import BeautifulSoup


# Private/reserved IP ranges that should not be accessed via fetch_url
_BLOCKED_NETWORKS = [
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("169.254.0.0/16"),
    ipaddress.ip_network("::1/128"),
    ipaddress.ip_network("fc00::/7"),
    ipaddress.ip_network("fe80::/10"),
]


def _is_private_ip(hostname: str) -> bool:
    """Check if a hostname resolves to a private/reserved IP address."""
    # Block localhost explicitly
    if hostname in ("localhost", "0.0.0.0"):
        return True
    try:
        addr = ipaddress.ip_address(hostname)
        return any(addr in network for network in _BLOCKED_NETWORKS)
    except ValueError:
        # Not an IP literal -- resolve via DNS and check the actual IP
        try:
            resolved = socket.getaddrinfo(hostname, None)
            for family, _, _, _, sockaddr in resolved:
                ip = ipaddress.ip_address(sockaddr[0])
                if any(ip in network for network in _BLOCKED_NETWORKS):
                    return True
        except (socket.gaierror, OSError):
            return True  # fail closed
        return False


def _validate_url(url: str) -> str:
    """Validate URL and reject requests to private/reserved IP ranges."""
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise ValueError(f"Unsupported URL scheme: {parsed.scheme}")
    hostname = parsed.hostname or ""
    if _is_private_ip(hostname):
        raise ValueError(f"Access to private/reserved IP range is blocked: {hostname}")
    return url


class SearchService:
    """联网搜索服务，支持 DuckDuckGo 搜索和网页抓取"""

    async def search(
        self, query: str, max_results: int = 5
    ) -> List[Dict[str, str]]:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                "https://html.duckduckgo.com/html/",
                params={"q": query},
                headers={"User-Agent": "Mozilla/5.0"},
                timeout=15,
            )
            response.raise_for_status()

        soup = BeautifulSoup(response.text, "html.parser")
        results = []
        for result in soup.select(".result")[:max_results]:
            title_tag = result.select_one(".result__title a")
            snippet_tag = result.select_one(".result__snippet")
            if title_tag:
                results.append({
                    "title": title_tag.get_text(strip=True),
                    "url": title_tag.get("href", ""),
                    "snippet": snippet_tag.get_text(strip=True) if snippet_tag else "",
                })
        return results

    async def fetch_url(
        self, url: str, max_length: int = 5000
    ) -> Dict[str, str]:
        _validate_url(url)

        async with httpx.AsyncClient() as client:
            response = await client.get(
                url,
                headers={"User-Agent": "Mozilla/5.0"},
                timeout=15,
                follow_redirects=False,
            )
            response.raise_for_status()

        # Only parse text/html responses
        content_type = response.headers.get("content-type", "")
        if "text/html" not in content_type:
            return {"title": url, "content": "", "url": url}

        soup = BeautifulSoup(response.text, "html.parser")
        for tag in soup(["script", "style", "nav", "footer", "header"]):
            tag.decompose()

        text = soup.get_text(separator="\n", strip=True)[:max_length]
        title = soup.title.string if soup.title else url
        return {"title": title, "content": text, "url": url}


search_service = SearchService()
