from typing import Optional, List, Dict, Any
import httpx
from bs4 import BeautifulSoup


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
        async with httpx.AsyncClient() as client:
            response = await client.get(
                url,
                headers={"User-Agent": "Mozilla/5.0"},
                timeout=15,
                follow_redirects=True,
            )
            response.raise_for_status()

        soup = BeautifulSoup(response.text, "html.parser")
        for tag in soup(["script", "style", "nav", "footer", "header"]):
            tag.decompose()

        text = soup.get_text(separator="\n", strip=True)[:max_length]
        title = soup.title.string if soup.title else url
        return {"title": title, "content": text, "url": url}


search_service = SearchService()
