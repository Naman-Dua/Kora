import requests
from bs4 import BeautifulSoup

def search_online(query):
    headers = {"User-Agent": "Mozilla/5.0"}
    url = f"https://www.google.com/search?q={query}"
    
    try:
        response = requests.get(url, headers=headers, timeout=5)
        soup = BeautifulSoup(response.text, 'html.parser')
        # Extracts the descriptive snippet from Google
        result = soup.find("div", class_="VwiC3b")
        return result.get_text() if result else "I found information but couldn't parse it, sir."
    except:
        return "I am unable to access the global grid at the moment."