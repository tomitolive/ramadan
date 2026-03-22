import json
import os
import re
import logging
import random
import argparse
from urllib.parse import unquote
from bs4 import BeautifulSoup
from core.utils import get_session, fetch, abs_url, TARGET_PROVIDERS, EXCLUDED_DOMAINS, BASE_URL

class BaseScraper:
    def __init__(self, name, categories, output_dir="data", file_size_limit=10 * 1024 * 1024, required_keywords=None):
        self.name = name
        self.categories = categories
        self.output_dir = output_dir
        self.output_file_base = os.path.join(output_dir, "results")
        self.file_size_limit = file_size_limit
        self.required_keywords = required_keywords or []
        
        self.logger = logging.getLogger(name)
        self.logger.setLevel(logging.INFO)
        if not self.logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)

        self.session = get_session()
        self.processed_series = set()
        self.seen_urls = set()
        self.global_file_state = {'filename': f"{self.output_file_base}_1.json", 'part': 1}
        
        if not os.path.exists(self.output_dir):
            os.makedirs(self.output_dir)

    def load_existing_data(self):
        p = 1
        while os.path.exists(f"{self.output_file_base}_{p}.json"):
            try:
                with open(f"{self.output_file_base}_{p}.json", "r", encoding="utf-8") as f:
                    for it in json.load(f):
                        u = it.get("url")
                        if u: self.seen_urls.add(abs_url(u))
                        if it.get("type") in ("series", "season"):
                            self.processed_series.add(abs_url(u))
            except Exception as e:
                self.logger.error(f"Error loading {self.output_file_base}_{p}.json: {e}")
            p += 1
        self.logger.info(f"Loaded {len(self.seen_urls)} seen URLs and {len(self.processed_series)} processed series.")

    def get_latest_file_info(self):
        part = 1
        while os.path.exists(f"{self.output_file_base}_{part}.json"):
            if os.path.getsize(f"{self.output_file_base}_{part}.json") < self.file_size_limit:
                break
            part += 1
        
        filename = f"{self.output_file_base}_{part}.json"
        data = []
        if os.path.exists(filename):
            try:
                with open(filename, "r", encoding="utf-8") as f:
                    data = json.load(f)
            except:
                data = []
        return filename, part, data

    def atomic_save(self, filename, data):
        tmp = filename + ".tmp"
        try:
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            os.replace(tmp, filename)
        except Exception as e:
            self.logger.error(f"Error saving {filename}: {e}")

    def save_and_rotate(self, results, current_info):
        filename, part = current_info
        self.atomic_save(filename, results)
        
        if os.path.exists(filename) and os.path.getsize(filename) > self.file_size_limit:
            self.logger.info(f"!!! File {filename} reached limit. Starting new part...")
            new_part = part + 1
            new_filename = f"{self.output_file_base}_{new_part}.json"
            results.clear()
            return new_filename, new_part
        return filename, part

    def extract_metadata(self, soup, url):
        meta = {"url": url, "title": "", "poster": "", "description": "", "year": "", "quality": "", "categories": []}
        t = soup.find("meta", property="og:title")
        if t: meta["title"] = t.get("content", "").replace("مشاهدة ", "").strip()
        elif soup.title: meta["title"] = soup.title.string.strip()
        
        img = soup.find("meta", property="og:image")
        if img: meta["poster"] = img.get("content", "")
        
        desc = soup.find("meta", property="og:description")
        if desc: meta["description"] = desc.get("content", "").strip()
        
        for c in soup.select(".categ, .category, .post-category a"):
            meta["categories"].append(c.get_text(strip=True))

        series_link = soup.select_one('a[href*="/series/"], a[href*="/mosalsal/"], a[href*="/season/"], .breadcrumb a[href*="/series/"]')
        if not series_link:
            for a in soup.find_all("a", href=True):
                txt = a.get_text(strip=True)
                if "جميع الحلقات" in txt or "كل الحلقات" in txt or "المسلسل" in txt:
                    series_link = a
                    break
        
        if series_link:
            meta["series_url"] = abs_url(series_link.get("href"))
        
        return meta

    def scrape_watch_links(self, url):
        html = fetch(self.session, url)
        if not html: return []
        servers = []
        match = re.search(r"JSON\.parse\('(\[.*?\])'\)", html)
        if match:
            try:
                raw = re.sub(r'\\u([0-9a-fA-F]{4})', lambda m: chr(int(m.group(1), 16)), match.group(1))
                for s in json.loads(raw):
                    u = s.get("url", "")
                    if u:
                        if u.startswith("/"): u = BASE_URL + u
                        servers.append({"name": s.get("name", "Server"), "url": abs_url(u)})
            except: pass
        if not servers:
            soup = BeautifulSoup(html, "html.parser")
            for iframe in soup.find_all("iframe"):
                src = iframe.get("src") or iframe.get("data-src")
                if src and src.startswith("https") and not any(ex in src for ex in EXCLUDED_DOMAINS):
                    servers.append({"name": "Embed", "url": src})
        return servers

    def scrape_episode_data(self, url):
        html = fetch(self.session, url)
        if not html: return [], []
        soup = BeautifulSoup(html, "html.parser")
        w_url, d_url = None, None
        for a in soup.find_all("a", href=True):
            h = abs_url(a["href"])
            if h and "/watch/" in h: w_url = h
            elif h and "/download/" in h: d_url = h
        watch = self.scrape_watch_links(w_url) if w_url else []
        dl = []
        if d_url:
            d_html = fetch(self.session, d_url)
            if d_html:
                dsoup = BeautifulSoup(d_html, "html.parser")
                for a in dsoup.select("a.btn-down, .servers a[href]"):
                    href = a.get("href")
                    if href and href.startswith("https") and not any(ex in href for ex in EXCLUDED_DOMAINS):
                        dl.append({"name": a.get_text(strip=True) or "DL", "url": href})
        return watch, dl

    def is_matching(self, meta):
        if not self.required_keywords:
            return True
        text_to_check = (meta['title'] + " " + " ".join(meta['categories'])).lower()
        return any(kw.lower() in text_to_check for kw in self.required_keywords)

    def process_item(self, url, results, parent_id=None, force_match=False):
        is_series = "/series/" in url or "/mosalsal/" in url
        is_season = "/season/" in url
        
        if url in self.seen_urls:
            if (is_series or is_season):
                self.logger.info(f"   [UPDATE] Checking for new episodes in: {url}")
            else:
                return

        self.logger.info(f"==> {url}")
        html = fetch(self.session, url)
        if not html: 
            self.logger.warning(f"   [FAIL] No HTML for {url}")
            return
        soup = BeautifulSoup(html, "html.parser")
        meta = self.extract_metadata(soup, url)

        # check if it matches the required keywords
        if not force_match and not parent_id and not self.is_matching(meta):
            self.logger.info(f"   [SKIP] Does not match requirements: {meta['title']}")
            return

        is_episode = "/episode/" in url or "/ep-" in url
        is_movie = "/film/" in url

        if is_episode and meta.get("series_url") and meta["series_url"] not in self.processed_series and meta["series_url"] != url:
            self.logger.info(f"   [REDIRECT] episode -> series: {meta['series_url']}")
            self.process_item(meta["series_url"], results, force_match=True)
            if meta["series_url"] not in self.processed_series:
                self.logger.warning(f"   [WARN] Redirect failed for {meta['series_url']}, falling back to standalone episode.")
            else:
                return

        def get_id(u, poster):
            m = re.search(r'/(\d+)', poster)
            return m.group(1) if m else str(abs(hash(u)))[:10]

        native_id = parent_id or get_id(url, meta['poster'])
        item_type = "series" if is_series else ("season" if is_season else ("movie" if is_movie else "episode"))

        if (is_series or is_season) and not parent_id:
            if url not in self.processed_series:
                self.logger.info(f"[*] SERIES/SEASON: {meta['title']}")
                results.append({
                    "id": native_id, "type": item_type, "title": meta["title"],
                    "poster": meta["poster"], "description": meta["description"], "url": url
                })
                self.processed_series.add(url)
                self.global_file_state['filename'], self.global_file_state['part'] = \
                    self.save_and_rotate(results, (self.global_file_state['filename'], self.global_file_state['part']))
            else:
                self.logger.info(f"[*] UPDATING SERIES/SEASON: {meta['title']}")

            child_urls = []
            curr = url
            while curr:
                pg = fetch(self.session, curr) if curr != url else html
                if not pg: break
                ps = BeautifulSoup(pg, "html.parser")
                for a in ps.select(".show-card, .box-item a, .ep-card a, .season-card a, .breadcrumb a"):
                    f = abs_url(a.get("href"))
                    if f and f not in self.seen_urls and ("/episode/" in f or "/ep-" in f or "/season/" in f or "/mosalsal/" in f or "/series/" in f):
                        if f == url: continue
                        if f not in child_urls: child_urls.append(f)
                
                if not child_urls:
                    for a in ps.find_all("a", href=True):
                        f = abs_url(a.get("href"))
                        if f and f not in self.seen_urls and ("/episode/" in f or "/ep-" in f or "/season/" in f):
                            if f == url: continue
                            if f not in child_urls: child_urls.append(f)

                next_btn = ps.select_one("a.next, .pagination .next a")
                curr = abs_url(next_btn.get("href")) if next_btn else None

            seasons = [u for u in child_urls if "/season/" in u]
            if seasons:
                def get_season_num(u):
                    last_part = unquote(u.rstrip('/').split('/')[-1])
                    nums = re.findall(r'(\d+)', last_part)
                    if nums: return int(nums[-1])
                    if "الاول" in last_part: return 1
                    if "الثاني" in last_part: return 2
                    if "الثالث" in last_part: return 3
                    return 0
                
                latest_season = max(seasons, key=get_season_num)
                self.logger.info(f"   [FILTER] Multiple seasons found ({len(seasons)}). Selecting latest: {latest_season}")
                child_urls = [latest_season]
            else:
                def sort_k(x):
                    parts = x.rstrip('/').split('/')
                    last_part = unquote(parts[-1])
                    nums = re.findall(r'(\d+)', last_part)
                    return int(nums[-1]) if nums else 0
                child_urls.sort(key=sort_k)
            
            self.logger.info(f"   [INFO] Found {len(child_urls)} children for {meta['title']}")
            for c in child_urls:
                self.process_item(c, results, native_id, force_match=True)
            return

        if is_episode or is_movie or is_season:
            if is_season:
                child_urls = []
                curr = url
                while curr:
                    pg = fetch(self.session, curr) if curr != url else html
                    if not pg: break
                    ps = BeautifulSoup(pg, "html.parser")
                    for a in ps.select(".show-card, .box-item a, .ep-card a"):
                        f = abs_url(a.get("href"))
                        if f and f not in self.seen_urls and ("/episode/" in f or "/ep-" in f):
                            if f not in child_urls: child_urls.append(f)
                    
                    next_btn = ps.select_one("a.next, .pagination .next a")
                    curr = abs_url(next_btn.get("href")) if next_btn else None
                
                def sort_k(x):
                    parts = x.rstrip('/').split('/')
                    last_part = unquote(parts[-1])
                    nums = re.findall(r'(\d+)', last_part)
                    return int(nums[-1]) if nums else 0
                child_urls.sort(key=sort_k)
                
                self.logger.info(f"   [INFO] Found {len(child_urls)} episodes in season {meta['title']}")
                for c in child_urls:
                    self.process_item(c, results, parent_id, force_match=True)
                return

            watch, dl = self.scrape_episode_data(url)
            item = {
                "id": native_id, "url": url, "type": "episode" if is_episode else "movie",
                "title": meta["title"], "poster": meta["poster"], "description": meta["description"],
                "watch_servers": watch, "download_links": dl
            }
            if parent_id: item["parent_id"] = parent_id
            results.append(item)
            self.seen_urls.add(url)
            self.global_file_state['filename'], self.global_file_state['part'] = \
                self.save_and_rotate(results, (self.global_file_state['filename'], self.global_file_state['part']))
            self.logger.info(f"   [OK] {meta['title']}")

    def run(self):
        parser = argparse.ArgumentParser(description=f"{self.name} Scraper")
        parser.add_argument("--mode", choices=["full", "updates"], default="updates", help="Scraping mode: full crawl or update check")
        parser.add_argument("--max-pages", type=int, default=50, help="Max pages for full crawl")
        args = parser.parse_args()

        self.load_existing_data()
        filename, part, results = self.get_latest_file_info()
        self.global_file_state = {'filename': filename, 'part': part}

        self.logger.info(f"=== [MODE: {args.mode.upper()}] Starting Scraper: {self.name} ===")

        if self.processed_series:
            self.logger.info(f"=== [START] CHECKING FOR UPDATES IN {len(self.processed_series)} EXISTING SERIES ===")
            series_to_check = list(self.processed_series)
            for s_url in series_to_check:
                self.process_item(s_url, results, force_match=True)
            self.logger.info("=== [FINISH] UPDATE CHECK COMPLETED ===")

        if args.mode == "full":
            for cat_url in self.categories:
                curr = cat_url
                page_num = 1
                self.logger.info(f"STARTING CATEGORY CRAWL: {curr}")
                while curr and page_num <= args.max_pages:
                    self.logger.info(f"--- Processing Category Page {page_num}/{args.max_pages} ---")
                    html = fetch(self.session, curr)
                    if not html: break
                    soup = BeautifulSoup(html, "html.parser")
                    links = []
                    for a in soup.select("a.show-card, .box-item a, article a, h2 a"):
                        h = abs_url(a.get("href"))
                        if h and h not in links: links.append(h)
                    for l in links:
                        # Random delay between items
                        time.sleep(random.uniform(1.5, 4.0))
                        self.process_item(l, results)
                    
                    page_num += 1
                    next_btn = soup.select_one("a.next, .pagination .next a")
                    curr = abs_url(next_btn.get("href")) if next_btn else None
                
                if page_num > args.max_pages:
                    self.logger.info(f"Reached max-pages ({args.max_pages}). Stopping category crawl.")
