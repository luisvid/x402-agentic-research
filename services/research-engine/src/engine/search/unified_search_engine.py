"""
Unified Search Engine: Single interface for all search providers.

Supports Tavily, Serper (Google Search), and DuckDuckGo.
Copied from parent project with sys.path manipulation removed.
"""

import logging
import os
from abc import ABC, abstractmethod
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

import requests

logger = logging.getLogger(__name__)


class SearchProvider(ABC):
    @abstractmethod
    def search(
        self,
        queries: List[str],
        days_back: int,
        max_results_per_query: int,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        pass

    @abstractmethod
    def get_provider_name(self) -> str:
        pass


class TavilyProvider(SearchProvider):
    def __init__(self):
        from tavily import TavilyClient

        api_key = os.getenv("TAVILY_API_KEY")
        if not api_key:
            raise ValueError("TAVILY_API_KEY environment variable is required")
        self.client = TavilyClient(api_key=api_key)
        logger.info("Tavily search provider initialized")

    def search(self, queries, days_back, max_results_per_query, start_date=None, end_date=None):
        articles = []
        for query in queries:
            try:
                search_params = {
                    "query": query,
                    "search_depth": "advanced",
                    "max_results": max_results_per_query,
                    "include_answer": False,
                    "include_raw_content": True,
                    "include_images": False,
                }
                if start_date and end_date:
                    search_params["start_date"] = start_date
                    search_params["end_date"] = end_date
                    search_params["topic"] = "news"
                elif days_back > 0:
                    computed_end = datetime.now()
                    computed_start = computed_end - timedelta(days=days_back)
                    search_params["start_date"] = computed_start.strftime("%Y-%m-%d")
                    search_params["end_date"] = computed_end.strftime("%Y-%m-%d")
                    search_params["topic"] = "news"

                response = self.client.search(**search_params)
                for result in response.get("results", []):
                    articles.append(
                        {
                            "title": result.get("title", ""),
                            "url": result.get("url", ""),
                            "content": result.get("content", ""),
                            "published_date": result.get("published_date"),
                            "source": "Tavily",
                            "score": result.get("score", 0.5),
                        }
                    )
            except Exception as e:
                logger.error(f"Tavily search failed for query '{query}': {e}")
        return articles

    def get_provider_name(self):
        return "Tavily"


class SerperProvider(SearchProvider):
    def __init__(self):
        self.api_key = os.getenv("SERPER_API_KEY")
        if not self.api_key:
            raise ValueError("SERPER_API_KEY environment variable is required")
        logger.info("Serper (Google Search) provider initialized")

    def search(self, queries, days_back, max_results_per_query, start_date=None, end_date=None):
        articles = []
        base_url = "https://google.serper.dev/search"
        headers = {"X-API-KEY": self.api_key, "Content-Type": "application/json"}

        if start_date and end_date:
            date_range = f"after:{start_date} before:{end_date}"
        else:
            computed_start = datetime.now() - timedelta(days=days_back)
            date_range = f"after:{computed_start.strftime('%Y-%m-%d')}"

        for query in queries:
            try:
                payload = {"q": f"{query} {date_range}", "num": max_results_per_query, "gl": "us", "hl": "en"}
                response = requests.post(base_url, json=payload, headers=headers, timeout=10)
                if response.status_code == 200:
                    data = response.json()
                    for item in data.get("organic", []):
                        articles.append(
                            {
                                "title": item.get("title", ""),
                                "url": item.get("link", ""),
                                "content": item.get("snippet", ""),
                                "published_date": None,
                                "source": "Google",
                                "score": 1.0,
                            }
                        )
            except Exception as e:
                logger.error(f"Serper search failed for query '{query}': {e}")
        return articles

    def get_provider_name(self):
        return "Serper"


class DuckDuckGoProvider(SearchProvider):
    def __init__(self):
        try:
            from ddgs import DDGS

            self.DDGS = DDGS
            logger.info("DuckDuckGo search provider initialized")
        except ImportError:
            raise ImportError("ddgs library not installed. Run: pip install ddgs")

    def search(self, queries, days_back, max_results_per_query, start_date=None, end_date=None):
        articles = []
        effective_days = days_back
        if start_date and end_date:
            try:
                s = datetime.strptime(start_date, "%Y-%m-%d")
                e = datetime.strptime(end_date, "%Y-%m-%d")
                effective_days = (e - s).days
            except ValueError:
                pass

        if effective_days <= 1:
            timelimit = "d"
        elif effective_days <= 7:
            timelimit = "w"
        elif effective_days <= 30:
            timelimit = "m"
        else:
            timelimit = None

        try:
            with self.DDGS() as ddgs:
                for query in queries:
                    try:
                        results = ddgs.text(
                            query=query,
                            region="us-en",
                            safesearch="off",
                            timelimit=timelimit,
                            max_results=max_results_per_query,
                        )
                        for result in results:
                            articles.append(
                                {
                                    "title": result.get("title", ""),
                                    "url": result.get("href", result.get("link", "")),
                                    "content": result.get("body", ""),
                                    "published_date": None,
                                    "source": "DuckDuckGo",
                                    "score": 0.5,
                                }
                            )
                    except Exception as e:
                        logger.error(f"DuckDuckGo search failed for query '{query}': {e}")
        except Exception as e:
            logger.error(f"DuckDuckGo initialization failed: {e}")
        return articles

    def get_provider_name(self):
        return "DuckDuckGo"


class UnifiedSearchEngine:
    def __init__(self):
        self.search_engine = os.getenv("SEARCH_ENGINE", "tavily").lower()
        if self.search_engine not in ["tavily", "serper", "duckduckgo"]:
            raise ValueError(f"Invalid SEARCH_ENGINE: '{self.search_engine}'")
        self.provider = self._create_provider()

    def _create_provider(self) -> SearchProvider:
        if self.search_engine == "serper":
            return SerperProvider()
        elif self.search_engine == "duckduckgo":
            return DuckDuckGoProvider()
        else:
            return TavilyProvider()

    def search(self, queries, days_back, max_results_per_query, start_date=None, end_date=None):
        return self.provider.search(queries, days_back, max_results_per_query, start_date=start_date, end_date=end_date)

    def get_provider_name(self):
        return self.provider.get_provider_name()
