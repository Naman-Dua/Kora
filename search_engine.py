import requests
from bs4 import BeautifulSoup
from urllib.parse import quote_plus

def search_online(query):
    # Bug fix 1: URL-encode the query so spaces/special chars don't break the URL.
    # Bug fix 2: Use DuckDuckGo HTML instead of Google — Google blocks scraping and
    #            frequently changes its CSS classes (like "VwiC3b"), causing silent failures.
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    url = f"https://html.duckduckgo.com/html/?q={quote_plus(query)}"

    try:
        response = requests.get(url, headers=headers, timeout=5)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        result = soup.find("a", class_="result__snippet")
        return result.get_text(strip=True) if result else "I found information but couldn't parse it, sir."
    except Exception:
        return "I am unable to access the global grid at the moment."