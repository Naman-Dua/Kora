import re
from urllib.parse import quote_plus

import requests
from bs4 import BeautifulSoup

SEARCH_PREFIX_PATTERNS = [
    re.compile(r"^(?:search for|search)\s+(.+)$", re.IGNORECASE),
    re.compile(r"^(?:look up|lookup)\s+(.+)$", re.IGNORECASE),
    re.compile(r"^(?:find online|search online for)\s+(.+)$", re.IGNORECASE),
    re.compile(r"^(?:web search)\s+(.+)$", re.IGNORECASE),
]


def extract_search_query(text):
    normalized = " ".join(str(text).strip().split())
    for pattern in SEARCH_PREFIX_PATTERNS:
        match = pattern.match(normalized)
        if match:
            return match.group(1).strip(" ?")
    return None


def is_search_request(text):
    return extract_search_query(text) is not None


def search_online(query, limit=3):
    """Return a small structured summary from DuckDuckGo HTML search."""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }
    url = f"https://html.duckduckgo.com/html/?q={quote_plus(query)}"

    try:
        response = requests.get(url, headers=headers, timeout=6)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")

        results = []
        for card in soup.select(".result")[:limit]:
            title_el = card.select_one(".result__a")
            snippet_el = card.select_one(".result__snippet")
            if not title_el:
                continue
            title = title_el.get_text(" ", strip=True)
            snippet = snippet_el.get_text(" ", strip=True) if snippet_el else ""
            link = title_el.get("href", "")
            results.append({"title": title, "snippet": snippet, "link": link})

        if not results:
            return {
                "query": query,
                "summary": "I found search results, but I could not parse them clearly.",
                "results": [],
            }

        lead = results[0]["snippet"] or f"The top result is {results[0]['title']}."
        return {"query": query, "summary": lead, "results": results}
    except Exception:
        return {
            "query": query,
            "summary": "I am unable to access the web right now.",
            "results": [],
        }


def format_search_response(payload):
    if isinstance(payload, str):
        return payload

    summary = payload.get("summary") or "I found a few results."
    results = payload.get("results") or []
    if not results:
        return summary

    top_bits = []
    for result in results[:3]:
        title = result.get("title")
        if title:
            top_bits.append(title)

    if not top_bits:
        return summary
    return f"{summary} Top results: {'; '.join(top_bits)}."
