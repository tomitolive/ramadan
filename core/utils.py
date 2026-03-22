import time
import logging

# ─── Config ─────────────────────────────────────────────────────
BASE_URL = "https://shaaheid4u.net"

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

def get_session():
    return cloudscraper.create_scraper()

def fetch(session, url, retries=3):
    for attempt in range(retries):
        try:
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

def abs_url(href, base=BASE_URL):
    if not href: return None
    url = href
    if not href.startswith("http"):
        url = base.rstrip("/") + "/" + href.lstrip("/")
    
    for dom in ["shhahiid4u.net", "shaaheed4u.net", "shaaheid4u.net"]:
        url = url.replace(dom, "shaaheid4u.net")
    return url
