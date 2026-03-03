import json
import os
import re
import time
import logging
import base64
from urllib.parse import urljoin, urlparse, parse_qs, unquote
from curl_cffi import requests
from bs4 import BeautifulSoup

# ─── Logging Setup ──────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("supreme_bot.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# ─── Config ─────────────────────────────────────────────────────
BASE_URL = "https://shaaheid4u.net"
# رابط قسم مسلسلات رمضان 2026 مباشرة
RAMADAN_CATEGORIES = [
    "https://shaaheid4u.net/category/مسلسلات-رمضان-2026"
]
MAX_PAGES = 7
OUTPUT_FILE_BASE = "ramadan_2026_results"
FILE_SIZE_LIMIT = 10 * 1024 * 1024  # 10MB
TARGET_PROVIDERS = [
    'fsdcmo', 'vinovo', 'mixdrop', 'doodstream', 'dood', 'streamwish',
    'filemoon', 'vidbm', 'vidmoly', 'streamtap', 'streamhg', 'streamvid',
    'streamlare', 'rabbitstream', 'fembed', 'voe', 'smoothpre', 'uqload',
    'vidoza', 'gounlimited', 'mp4upload', 'uptobox', 'ok.ru', 'dailymotion',
    'm1xdrop', 'mxdrop', 'krakenfiles', 'upn.one', 'shiid4u', 'earnvids',
    'savefiles', 'upshare', 'upstream', 'vidguard', 'vtube', 'vidlox', 'vk',
    'fdewsdc', 'dsvplay', 'streamtape', 'clicknupload', 'megaup', 'ddownload',
    'uploady'
]
EXCLUDED_DOMAINS = [
    'google.com', 'googleapis.com', 'gstatic.com', 'facebook.com',
    'twitter.com', 'instagram.com', 'schema.org', 'w3.org',
    'wordpress.org', 'gravatar.com', 'jquery.com', 'cloudflare.com',
    'doubleclick.net', 'google-analytics.com', 'youtube.com',
    'googletagmanager.com', 'fontawesome.com', 'intelligenceadx.com',
    'adsco.re', 'ipify.org', 'recaptcha'
]

# ─── Global State ───────────────────────────────────────────────
global_file_state = {'filename': f"{OUTPUT_FILE_BASE}_1.json", 'part': 1}
processed_series = set()

# ─── Session ────────────────────────────────────────────────────
def get_session():
    sess = requests.Session(impersonate="chrome120")
    sess.headers.update({
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "ar,en-US;q=0.9,en;q=0.8",
        "DNT": "1",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
    })
    return sess

def fetch(session, url, retries=3):
    for attempt in range(retries):
        try:
            # إضافة تأخير بسيط لتجنب الحظر
            time.sleep(1.5)
            resp = session.get(url, timeout=20, allow_redirects=True)
            if resp.status_code == 200: 
                return resp.text
            else:
                logger.warning(f"Fetch {url} failed with status {resp.status_code} (Attempt {attempt+1}/{retries})")
                if resp.status_code in (403, 503):
                    time.sleep(10)
        except Exception as e:
            logger.error(f"Fetch {url} error: {e} (Attempt {attempt+1}/{retries})")
            time.sleep(2)
    return None

def abs_url(href):
    if not href: return None
    url = href
    if not href.startswith("http"):
        url = BASE_URL.rstrip("/") + "/" + href.lstrip("/")
    
    # Normalize domain to BASE_URL domain
    for dom in ["shhahiid4u.net", "shaaheed4u.net", "shaaheid4u.net"]:
        url = url.replace(dom, "shaaheid4u.net")
    return url

# ─── Saving Logic ───────────────────────────────────────────────
def get_latest_file_info():
    """يرجع المسار الحالي، الجزء الحالي، والبيانات المحملة"""
    part = 1
    while os.path.exists(f"{OUTPUT_FILE_BASE}_{part}.json"):
        if os.path.getsize(f"{OUTPUT_FILE_BASE}_{part}.json") < FILE_SIZE_LIMIT:
            break
        part += 1
    
    filename = f"{OUTPUT_FILE_BASE}_{part}.json"
    data = []
    if os.path.exists(filename):
        try:
            with open(filename, "r", encoding="utf-8") as f:
                data = json.load(f)
        except:
            data = []
    return filename, part, data

def atomic_save(filename, data):
    tmp = filename + ".tmp"
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        os.replace(tmp, filename)
    except Exception as e:
        logger.error(f"Error saving {filename}: {e}")

def save_and_rotate(results, current_info):
    """حفظ النتائج وتغيير الملف إذا تجاوز 10MB"""
    filename, part = current_info
    atomic_save(filename, results)
    
    if os.path.exists(filename) and os.path.getsize(filename) > FILE_SIZE_LIMIT:
        logger.info(f"!!! File {filename} reached 10MB. Starting new part...")
        new_part = part + 1
        new_filename = f"{OUTPUT_FILE_BASE}_{new_part}.json"
        # تصفية القائمة لبدء ملف جديد
        results.clear()
        return new_filename, new_part
    return filename, part

# ─── Extraction ─────────────────────────────────────────────────
def extract_metadata(soup, url):
    meta = {"url": url, "title": "", "poster": "", "description": "", "year": "2026", "quality": "", "categories": []}
    t = soup.find("meta", property="og:title")
    if t: meta["title"] = t.get("content", "").replace("مشاهدة ", "").strip()
    elif soup.title: meta["title"] = soup.title.string.strip()
    
    img = soup.find("meta", property="og:image")
    if img: meta["poster"] = img.get("content", "")
    
    desc = soup.find("meta", property="og:description")
    if desc: meta["description"] = desc.get("content", "").strip()
    
    # استخراج التصنيفات
    for c in soup.select(".categ, .category, .post-category a"):
        meta["categories"].append(c.get_text(strip=True))

    # محاولة العثور على رابط المسلسل من صفحة الحلقة
    series_link = soup.select_one('a[href*="/series/"], a[href*="/mosalsal/"], a[href*="/season/"], .breadcrumb a[href*="/series/"]')
    if not series_link:
        # البحث عن نصوص معينة
        for a in soup.find_all("a", href=True):
            txt = a.get_text(strip=True)
            if "جميع الحلقات" in txt or "كل الحلقات" in txt or "المسلسل" in txt:
                series_link = a
                break
    
    if series_link:
        meta["series_url"] = abs_url(series_link.get("href"))
    
    return meta

def scrape_watch_links(session, url):
    html = fetch(session, url)
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

def scrape_episode_data(session, url):
    html = fetch(session, url)
    if not html: return [], []
    soup = BeautifulSoup(html, "html.parser")
    w_url, d_url = None, None
    for a in soup.find_all("a", href=True):
        h = abs_url(a["href"])
        if h and "/watch/" in h: w_url = h
        elif h and "/download/" in h: d_url = h
    watch = scrape_watch_links(session, w_url) if w_url else []
    dl = []
    if d_url:
        d_html = fetch(session, d_url)
        if d_html:
            dsoup = BeautifulSoup(d_html, "html.parser")
            for a in dsoup.select("a.btn-down, .servers a[href]"):
                href = a.get("href")
                if href and href.startswith("https") and not any(ex in href for ex in EXCLUDED_DOMAINS):
                    dl.append({"name": a.get_text(strip=True) or "DL", "url": href})
    return watch, dl

# ─── Process Item ───────────────────────────────────────────────
def process_item(session, url, results, seen_urls, parent_id=None, force_ramadan=False):
    global global_file_state
    
    # السماح للمسلسلات بالدخول حتى لو شوهدت في قائمة الفئات
    is_series = "/series/" in url or "/mosalsal/" in url
    is_season = "/season/" in url
    
    if url in seen_urls:
        if (is_series or is_season):
            # نستمر لمعالجة المسلسل للتأكد من وجود جميع الحلقات (تحديث)
            logger.info(f"   [UPDATE] Checking for new episodes in: {url}")
        else:
            return

    # تتبع التنفيذ
    logger.info(f"==> {url}")
    html = fetch(session, url)
    if not html: 
        logger.warning(f"   [FAIL] No HTML for {url}")
        return
    soup = BeautifulSoup(html, "html.parser")
    meta = extract_metadata(soup, url)

    # فلترة رمضان 2026
    is_ramadan = force_ramadan or any("رمضان 2026" in c for c in meta['categories']) or "رمضان 2026" in meta['title']
    if not is_ramadan and not parent_id:
        logger.info(f"   [SKIP] Not Ramadan 2026: {meta['title']}")
        # لا نقوم بإضافة الرابط لـ seen_urls هنا لنسمح للمحاولات الأخرى (عبر التوجيه) بالدخول
        return

    is_series = "/series/" in url or "/mosalsal/" in url
    is_season = "/season/" in url
    is_episode = "/episode/" in url or "/ep-" in url

    # إذا كانت حلقة، حاول الوصول للمسلسل أولاً
    if is_episode and meta.get("series_url") and meta["series_url"] not in processed_series and meta["series_url"] != url:
        logger.info(f"   [REDIRECT] episode -> series: {meta['series_url']}")
        process_item(session, meta["series_url"], results, seen_urls, force_ramadan=is_ramadan)
        if meta["series_url"] not in processed_series:
            logger.warning(f"   [WARN] Redirect failed for {meta['series_url']}, falling back to standalone episode.")
        else:
            return

    def get_id(u, poster):
        m = re.search(r'/(\d+)', poster)
        return m.group(1) if m else str(abs(hash(u)))[:10]

    native_id = parent_id or get_id(url, meta['poster'])
    item_type = "series" if is_series else ("season" if is_season else ("movie" if "/film/" in url else "episode"))

    # حفظ المسلسل أو الموسم أو الفيلم
    if (is_series or is_season) and not parent_id:
        if url not in processed_series:
            logger.info(f"[*] SERIES/SEASON: {meta['title']}")
            results.append({
                "id": native_id, "type": item_type, "title": meta["title"],
                "poster": meta["poster"], "description": meta["description"], "url": url
            })
            processed_series.add(url)
            global_file_state['filename'], global_file_state['part'] = \
                save_and_rotate(results, (global_file_state['filename'], global_file_state['part']))
        else:
            logger.info(f"[*] UPDATING SERIES/SEASON: {meta['title']}")

        # جمع الأبناء (حلقات أو مواسم)
        child_urls = []
        curr = url
        while curr:
            pg = fetch(session, curr) if curr != url else html
            if not pg: break
            ps = BeautifulSoup(pg, "html.parser")
            # البحث عن الروابط في الكروت والشبكة أولاً
            for a in ps.select(".show-card, .box-item a, .ep-card a, .season-card a, .breadcrumb a"):
                f = abs_url(a.get("href"))
                if f and f not in seen_urls and ("/episode/" in f or "/ep-" in f or "/season/" in f or "/mosalsal/" in f or "/series/" in f):
                    if f == url: continue
                    if f not in child_urls: child_urls.append(f)
            
            # إذا لم يجد شيئاً، ابحث في كل الروابط
            if not child_urls:
                for a in ps.find_all("a", href=True):
                    f = abs_url(a.get("href"))
                    if f and f not in seen_urls and ("/episode/" in f or "/ep-" in f or "/season/" in f):
                        if f == url: continue
                        if f not in child_urls: child_urls.append(f)

            next_btn = ps.select_one("a.next, .pagination .next a")
            curr = abs_url(next_btn.get("href")) if next_btn else None

        # Filter for latest season if multiple exist
        seasons = [u for u in child_urls if "/season/" in u]
        if seasons:
            def get_season_num(u):
                last_part = unquote(u.rstrip('/').split('/')[-1])
                nums = re.findall(r'(\d+)', last_part)
                if nums: return int(nums[-1])
                # Fallback to title check if URL doesn't have a clear number
                if "الاول" in last_part: return 1
                if "الثاني" in last_part: return 2
                if "الثالث" in last_part: return 3
                return 0
            
            latest_season = max(seasons, key=get_season_num)
            logger.info(f"   [FILTER] Multiple seasons found ({len(seasons)}). Selecting latest: {latest_season}")
            # Keep ONLY the latest season URL. Standalone episodes are usually included in the season.
            child_urls = [latest_season]
        else:
            # ترتيب الحلقات رقمياً بشكل دقيق إذا لم تكن هناك مواسم
            def sort_k(x):
                parts = x.rstrip('/').split('/')
                last_part = unquote(parts[-1])
                nums = re.findall(r'(\d+)', last_part)
                if nums:
                    return int(nums[-1])
                return 0
            child_urls.sort(key=sort_k)
        
        logger.info(f"   [INFO] Found {len(child_urls)} children for {meta['title']}")
        for c in child_urls:
            process_item(session, c, results, seen_urls, native_id, force_ramadan=True)
        return

    # معالجة حلقة أو فيلماً أو موسماً (كطفل)
    if is_episode or "/film/" in url or is_season:
        if is_season:
            # إذا كان موسماً داخل مسلسل، نوسعه أيضاً
            child_urls = []
            curr = url
            while curr:
                pg = fetch(session, curr) if curr != url else html
                if not pg: break
                ps = BeautifulSoup(pg, "html.parser")
                for a in ps.select(".show-card, .box-item a, .ep-card a"):
                    f = abs_url(a.get("href"))
                    if f and f not in seen_urls and ("/episode/" in f or "/ep-" in f):
                        if f not in child_urls: child_urls.append(f)
                
                if not child_urls:
                    for a in ps.find_all("a", href=True):
                        f = abs_url(a.get("href"))
                        if f and f not in seen_urls and ("/episode/" in f or "/ep-" in f):
                            if f not in child_urls: child_urls.append(f)

                next_btn = ps.select_one("a.next, .pagination .next a")
                curr = abs_url(next_btn.get("href")) if next_btn else None
            
            def sort_k(x):
                parts = x.rstrip('/').split('/')
                last_part = unquote(parts[-1])
                nums = re.findall(r'(\d+)', last_part)
                return int(nums[-1]) if nums else 0
            child_urls.sort(key=sort_k)
            
            logger.info(f"   [INFO] Found {len(child_urls)} episodes in season {meta['title']}")
            for c in child_urls:
                process_item(session, c, results, seen_urls, parent_id, force_ramadan=True)
            return

        # معالجة حلقة واحدة
        watch, dl = scrape_episode_data(session, url)
        # استخراج رقم الحلقة من العنوان لترتيب أفضل في الـ JSON إذا لزم الأمر
        ep_match = re.search(r'الحلقة\s+(\d+)', meta['title'])
        ep_num = int(ep_match.group(1)) if ep_match else 0

        item = {
            "id": native_id, "url": url, "type": "episode" if is_episode else "movie",
            "title": meta["title"], "poster": meta["poster"], "description": meta["description"],
            "watch_servers": watch, "download_links": dl
        }
        if parent_id: item["parent_id"] = parent_id
        results.append(item)
        seen_urls.add(url)
        global_file_state['filename'], global_file_state['part'] = \
            save_and_rotate(results, (global_file_state['filename'], global_file_state['part']))
        logger.info(f"   [OK] {meta['title']}")

def main():
    global global_file_state
    session = get_session()
    filename, part, results = get_latest_file_info()
    global_file_state = {'filename': filename, 'part': part}
    seen_urls = set()
    
    # تحميل التاريخ
    p = 1
    while os.path.exists(f"{OUTPUT_FILE_BASE}_{p}.json"):
        try:
            with open(f"{OUTPUT_FILE_BASE}_{p}.json", "r", encoding="utf-8") as f:
                for it in json.load(f):
                    u = it.get("url")
                    if u: seen_urls.add(abs_url(u))
                    if it.get("type") in ("series", "season"):
                        processed_series.add(abs_url(u))
        except: pass
        p += 1

    # جديد: التحقق من وجود حلقات جديدة للمسلسلات الموجودة مسبقاً قبل بدء الكشط العادي
    if processed_series:
        logger.info(f"=== [START] CHECKING FOR UPDATES IN {len(processed_series)} EXISTING SERIES ===")
        # نحولها لقائمة لتجنب مشاكل التغيير أثناء الدوران إذا حدث
        series_to_check = list(processed_series)
        for s_url in series_to_check:
            logger.info(f"Checking update for: {s_url}")
            # استدعاء process_item للمسلسل سيقوم بالتنقيب عن حلقات جديدة
            process_item(session, s_url, results, seen_urls, force_ramadan=True)
        logger.info("=== [FINISH] UPDATE CHECK COMPLETED ===")

    for cat_url in RAMADAN_CATEGORIES:
        curr = cat_url
        page_num = 1
        logger.info(f"STARTING CATEGORY: {curr}")
        while curr and page_num <= MAX_PAGES:
            logger.info(f"--- Processing Category Page {page_num} ---")
            html = fetch(session, curr)
            if not html: break
            soup = BeautifulSoup(html, "html.parser")
            links = []
            for a in soup.select("a.show-card, .box-item a, article a, h2 a"):
                h = abs_url(a.get("href"))
                if h and h not in links: links.append(h)
            for l in links:
                process_item(session, l, results, seen_urls, force_ramadan=True)
            
            page_num += 1
            next_btn = soup.select_one("a.next, .pagination .next a")
            curr = abs_url(next_btn.get("href")) if next_btn else None
        
        if page_num > MAX_PAGES:
            logger.info(f"Reached MAX_PAGES ({MAX_PAGES}). Stopping.")

if __name__ == "__main__":
    main()