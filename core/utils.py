import time
import logging

# ─── Config ─────────────────────────────────────────────────────
BASE_URL = "https://web32218x.faselhdx.bid"

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

logger = logging.getLogger(__name__)

import cloudscraper
import random

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:123.0) Gecko/20100101 Firefox/123.0",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_3_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.3.1 Mobile/15E148 Safari/604.1"
]

def get_session():
    # Use a random browser fingerprint to avoid detection
    browser = random.choice(['chrome', 'firefox'])
    return cloudscraper.create_scraper(
        browser={'browser': browser, 'platform': 'windows', 'mobile': False}
    )

def fetch(session, url, retries=3):
    for attempt in range(retries):
        try:
            # Longer and randomized delay between requests
            delay = random.uniform(2.0, 5.0)
            time.sleep(delay)
            
            # Rotate User-Agent manually for extra safety
            session.headers.update({"User-Agent": random.choice(USER_AGENTS)})
            
            resp = session.get(url, timeout=30, allow_redirects=True)
            if resp.status_code == 200: 
                return resp.text
            elif resp.status_code in (403, 503):
                # Exponential backoff on protection/block
                wait_time = (attempt + 1) * 30 
                logger.warning(f"Blocking detected ({resp.status_code}) for {url}. Waiting {wait_time}s...")
                time.sleep(wait_time)
            else:
                logger.warning(f"Fetch {url} failed with status {resp.status_code} (Attempt {attempt+1}/{retries})")
                time.sleep(5)
        except Exception as e:
            logger.error(f"Fetch {url} error: {e} (Attempt {attempt+1}/{retries})")
            time.sleep(10)
    return None

def abs_url(href, base=BASE_URL):
    if not href: return None
    url = href
    if not href.startswith("http"):
        url = base.rstrip("/") + "/" + href.lstrip("/")
    
    for dom in ["shhahiid4u.net", "shaaheed4u.net", "shaaheid4u.net", "faselhd.club", "faselhd.pro", "fasel-hd.cam"]:
        url = url.replace(dom, "web32218x.faselhdx.bid")
    
    # Special case for 'faselhd' without extension, avoid replacing if already new domain
    if "faselhd" in url and "web32218x.faselhdx.bid" not in url:
        url = url.replace("faselhd", "web32218x.faselhdx.bid")
    return url
