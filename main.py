import threading
import queue
import urllib.request
from urllib.parse import urljoin, urlparse
from html.parser import HTMLParser
import time

# --- SHARED STATE & ARCHITECTURE ---
MAX_QUEUE_SIZE = 1000 # Back pressure yönetimi
url_queue = queue.Queue(maxsize=MAX_QUEUE_SIZE)
visited_urls = set()
search_index = [] # Triples: (relevant_url, origin_url, depth)
index_lock = threading.Lock()
visited_lock = threading.Lock()

class LinkParser(HTMLParser):
    def __init__(self, base_url):
        super().__init__()
        self.base_url = base_url
        self.links = []

    def handle_starttag(self, tag, attrs):
        if tag == 'a':
            for attr, value in attrs:
                if attr == 'href':
                    full_url = urljoin(self.base_url, value)
                    if full_url.startswith('http'):
                        self.links.append(full_url)

# --- INDEXER (CRAWLER) AGENT ---
def index_worker():
    while True:
        try:
            # Kuyruktan 4 değer bekliyoruz
            current_url, origin_url, current_depth, max_depth = url_queue.get(timeout=2)
        except queue.Empty:
            continue

        if current_depth > max_depth:
            url_queue.task_done()
            continue

        with visited_lock:
            if current_url in visited_urls:
                url_queue.task_done()
                continue
            visited_urls.add(current_url)

        try:
            # "Hanged" ve "Failed" bağlantıları engellemek için timeout
            req = urllib.request.Request(current_url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=3) as response:
                html = response.read().decode('utf-8', errors='ignore')
                
                # İndekse ekle
                with index_lock:
                    search_index.append((current_url, origin_url, current_depth))
                
                # Yeni linkleri bul ve kuyruğa ekle
                if current_depth < max_depth:
                    parser = LinkParser(current_url)
                    parser.feed(html)
                    for link in parser.links:
                        try:
                            # Back pressure: Kuyruk doluysa bekler
                            # DÜZELTME: max_depth eklendi
                            url_queue.put((link, origin_url, current_depth + 1, max_depth), timeout=1)
                        except queue.Full:
                            pass # Back pressure status: Drop link if queue is consistently full
        except Exception as e:
            pass # Bağlantı hatası, atla.
        finally:
            url_queue.task_done()
            
            
def index(origin, k):
    print(f"[*] Starting indexing for {origin} with depth {k}...")
    url_queue.put((origin, origin, 0, int(k)))

# --- SEARCH AGENT ---
def search(query):
    results = []
    query = query.lower()
    with index_lock:
        for relevant_url, origin_url, depth in search_index:
            if query in relevant_url.lower():
                results.append((relevant_url, origin_url, depth))
    return results

# --- CLI & INTERFACE AGENT ---
def cli():
    print("Welcome to AI Web Crawler. Commands: index <url> <depth>, search <query>, status, exit")
    
    # Arka planda crawler thread'lerini başlat
    for _ in range(5):
        t = threading.Thread(target=index_worker, daemon=True)
        t.start()

    while True:
        try:
            cmd_input = input("crawler> ").strip().split(" ", 2)
            if not cmd_input or cmd_input[0] == "": continue
            
            cmd = cmd_input[0].lower()
            
            if cmd == "exit":
                print("Exiting...")
                break
            elif cmd == "index" and len(cmd_input) == 3:
                index(cmd_input[1], cmd_input[2])
            elif cmd == "search" and len(cmd_input) >= 2:
                term = " ".join(cmd_input[1:])
                res = search(term)
                print(f"\n--- Search Results for '{term}' ---")
                for r in res:
                    print(f"URL: {r[0]} | Origin: {r[1]} | Depth: {r[2]}")
                print(f"Total found: {len(res)}\n")
            elif cmd == "status":
                print(f"Queue depth (Back pressure): {url_queue.qsize()} / {MAX_QUEUE_SIZE}")
                print(f"Total indexed pages: {len(search_index)}")
                print(f"Unique URLs visited: {len(visited_urls)}")
            else:
                print("Invalid command.")
        except KeyboardInterrupt:
            break

if __name__ == "__main__":
    cli()