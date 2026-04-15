import requests
from bs4 import BeautifulSoup

def search_online(query):
    # Headers to mimic a real browser request
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    
    # Target Google Search
    search_url = f"https://www.google.com/search?q={query}"
    
    try:
        response = requests.get(search_url, headers=headers, timeout=10)
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Look for the primary description snippets (commonly in 'VwiC3b' or 'kno-rnc' classes)
        result = soup.find("div", class_="VwiC3b") 
        
        if result:
            return result.get_text()
        else:
            # Fallback to general paragraph if snippet is missing
            return "I have accessed the network, but the data is fragmented. I could not extract a clear summary, sir."
            
    except Exception as e:
        return f"Connection error: {e}"