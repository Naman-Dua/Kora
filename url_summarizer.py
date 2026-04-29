"""URL content summarizer — fetch page, summarize with local LLM."""

import re
import requests
from bs4 import BeautifulSoup

URL_SUMMARIZE_PATTERNS = [
    re.compile(r"^summarize (?:this )?(?:url|page|link|site|website)\s+(https?://\S+)$", re.I),
    re.compile(r"^(?:what(?:'s| is) (?:on|at)|read|summarize)\s+(https?://\S+)$", re.I),
    re.compile(r"^(?:tldr|tl;dr|summary of)\s+(https?://\S+)$", re.I),
]


def is_url_summarize_request(text):
    normalized = " ".join(str(text).strip().split())
    return any(p.match(normalized) for p in URL_SUMMARIZE_PATTERNS)


def _extract_url(text):
    normalized = " ".join(str(text).strip().split())
    for pattern in URL_SUMMARIZE_PATTERNS:
        m = pattern.match(normalized)
        if m:
            return m.group(1).strip()
    return None

from intelligent_cache import cache_api_response

@cache_api_response(ttl=3600) # Cache webpage content for 1 hour
def _fetch_text(url, max_chars=4000):
    try:
        r = requests.get(url, timeout=10, headers={"User-Agent": "Mozilla/5.0"})
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")
        for tag in soup(["script", "style", "nav", "footer", "header", "aside"]):
            tag.decompose()
        return soup.get_text(" ", strip=True)[:max_chars]
    except Exception:
        return None


def handle_url_summarize_command(text):
    import ollama
    from settings import get_setting

    url = _extract_url(text)
    if not url:
        return None

    content = _fetch_text(url)
    if not content:
        return {"action": "url_summarize", "reply": f"Could not fetch content from {url}."}

    model = get_setting("model_name", "llama3.1:8b")
    try:
        r = ollama.generate(
            model=model,
            prompt=f"Summarize in 3-5 sentences, no formatting:\n\n{content[:3000]}",
        )
        summary = r["response"].strip()
        return {"action": "url_summarize", "reply": f"Summary of {url}: {summary}"}
    except Exception as e:
        return {"action": "url_summarize", "reply": f"Could not summarize: {e}"}
