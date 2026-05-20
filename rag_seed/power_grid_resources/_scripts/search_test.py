import urllib.request
import urllib.parse
import re
from bs4 import BeautifulSoup

def search_bing(query):
    url = "https://cn.bing.com/search?q=" + urllib.parse.quote(query)
    req = urllib.request.Request(
        url, 
        headers={'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'}
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as response:
            html = response.read().decode('utf-8')
            soup = BeautifulSoup(html, 'html.parser')
            results = []
            for li in soup.find_all('li', class_='b_algo'):
                h2 = li.find('h2')
                if h2:
                    a = h2.find('a')
                    if a and a.get('href'):
                        title = a.get_text()
                        link = a.get('href')
                        results.append({'title': title, 'link': link})
            return results
    except Exception as e:
        print(f"Error searching for {query}: {e}")
        return []

if __name__ == '__main__':
    q = "建设工程质量管理条例 pdf"
    print(f"Searching for: {q}")
    for res in search_bing(q):
        print(res)
