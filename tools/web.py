import requests
import time
from urllib.parse import urlparse
from bs4 import BeautifulSoup
from typing import Dict, List, Any
from tools.base import BaseTool
from core.config import get_web_config

class WebSearchTool(BaseTool):
    name = "web.search"
    description = "Search the web for information. Args: query (str), top_k (int)"
    args_schema = {
        "query": "The search query string",
        "top_k": "Number of results to return (default 5)"
    }

    def run(self, query: str, top_k: int = 5) -> str:
        config = get_web_config()
        if not config.get("enabled", False):
            return "Error: Web tools are disabled in configuration."

        # Simple DuckDuckGo HTML scraper for MVP
        # In production, use a real API like Google Custom Search or Bing Search API
        url = "https://html.duckduckgo.com/html/"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }
        data = {"q": query}
        
        try:
            start_time = time.time()
            response = requests.post(url, data=data, headers=headers, timeout=config.get("timeout_seconds", 10))
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, "html.parser")
            results = []
            
            for result in soup.find_all("div", class_="result__body", limit=top_k):
                title_tag = result.find("a", class_="result__a")
                snippet_tag = result.find("a", class_="result__snippet")
                
                if title_tag and snippet_tag:
                    results.append({
                        "title": title_tag.get_text(strip=True),
                        "url": title_tag["href"],
                        "snippet": snippet_tag.get_text(strip=True)
                    })
            
            output = {
                "type": "web_search",
                "query": query,
                "results": results,
                "fetched_at": time.strftime("%Y-%m-%dT%H:%M:%S%z")
            }
            
            # If no results found (maybe DDG blocked us or changed layout), return error hint
            if not results:
                # Fallback hint
                return f"No results found for '{query}'. (Note: This MVP tool uses a basic scraper which might be blocked. Please configure a real Search API in production.)"
                
            return str(output)
            
        except Exception as e:
            return f"Error performing web search: {str(e)}"

class WebFetchTool(BaseTool):
    name = "web.fetch"
    description = "Fetch and extract text content from a URL. Args: url (str)"
    args_schema = {
        "url": "The URL to fetch"
    }

    def run(self, url: str) -> str:
        config = get_web_config()
        if not config.get("enabled", False):
            return "Error: Web tools are disabled in configuration."

        # Check allowed domains
        allowed_domains = config.get("allowed_domains", [])
        domain = urlparse(url).netloc
        # Simple domain check: exact match or endswith for subdomains
        # e.g. "github.com" matches "github.com" and "gist.github.com"
        # Removing 'www.' for check might be safer
        domain_clean = domain.replace("www.", "")
        
        is_allowed = False
        if not allowed_domains: # If empty, maybe allow all? No, "Security First" -> deny all
             pass
        else:
            for allowed in allowed_domains:
                if domain_clean == allowed or domain_clean.endswith("." + allowed):
                    is_allowed = True
                    break
        
        if not is_allowed:
            return f"Error: Domain '{domain}' is not in the allowed whitelist."

        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }

        try:
            response = requests.get(url, headers=headers, timeout=config.get("timeout_seconds", 10))
            response.raise_for_status()
            
            # Parse content
            soup = BeautifulSoup(response.text, "html.parser")
            
            # Remove script and style elements
            for script in soup(["script", "style", "nav", "footer", "header", "aside"]):
                script.decompose()
                
            text = soup.get_text(separator="\n")
            
            # Clean up text
            lines = (line.strip() for line in text.splitlines())
            chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
            text = '\n'.join(chunk for chunk in chunks if chunk)
            
            # Truncate
            max_len = config.get("max_content_length", 4000)
            if len(text) > max_len:
                text = text[:max_len] + "... [Truncated]"
                
            output = {
                "type": "web_fetch",
                "url": url,
                "content": text,
                "fetched_at": time.strftime("%Y-%m-%dT%H:%M:%S%z")
            }
            
            return str(output)

        except Exception as e:
            return f"Error fetching URL: {str(e)}"
