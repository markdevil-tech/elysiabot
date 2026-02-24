"""
Internet search service using DuckDuckGo.
No API key required.
"""
import logging
from typing import List, Dict

logger = logging.getLogger(__name__)


class SearchService:
    """Search the internet using DuckDuckGo."""

    async def search(self, query: str, max_results: int = 5) -> List[Dict]:
        """Search DuckDuckGo and return results."""
        try:
            from duckduckgo_search import AsyncDDGS

            results = []
            async with AsyncDDGS() as ddgs:
                async for r in ddgs.atext(query, max_results=max_results, region="id-id"):
                    results.append({
                        "title": r.get("title", ""),
                        "body": r.get("body", ""),
                        "url": r.get("href", ""),
                    })
            return results
        except Exception as e:
            logger.error(f"Search error: {e}")
            return [{"title": "Error", "body": f"Gagal mencari: {str(e)}", "url": ""}]

    def format_results(self, results: List[Dict]) -> str:
        """Format search results for LLM context."""
        if not results:
            return "Tidak ada hasil pencarian ditemukan."

        parts = []
        for i, r in enumerate(results, 1):
            parts.append(f"{i}. {r['title']}\n   {r['body']}\n   🔗 {r['url']}")
        return "\n\n".join(parts)

    async def search_formatted(self, query: str, max_results: int = 5) -> str:
        """Search and return formatted string."""
        results = await self.search(query, max_results)
        return self.format_results(results)
