import os
import re
import time
import random
import logging
from datetime import datetime, timezone
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright
import pytz

BASE_URL = "https://www.heraldscotland.com"
POLITICS_URL = f"{BASE_URL}/politics/"

def normalize_url(url):
    """
    Extracts the article ID (e.g., 12345678) from a Herald article URL.
    Falls back to full normalized URL if no match.
    """
    url = url.strip().split('?')[0].rstrip('/').lower()
    match = re.search(r'/(\d{6,})', url)
    return match.group(1) if match else url

def fetch_article_urls():
    """
    Uses Playwright to scrape article URLs from the Herald's politics section.
    Filters for URLs that match expected article patterns.
    """
    try:
        time.sleep(random.uniform(1.5, 3.5))
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True, args=["--no-sandbox"])
            page = browser.new_page()
            page.goto(POLITICS_URL, timeout=30000, wait_until="domcontentloaded")
            page.wait_for_timeout(5000)
            html = page.content()
            browser.close()

        soup = BeautifulSoup(html, 'lxml')
        urls = set()
        for link in soup.find_all('a', href=True):
            href = link['href'].split('#')[0]
            if not href.startswith('/'):
                continue
            if not re.search(r'/\d{6,}', href):  # Relaxed to match 6+ digit IDs
                logging.debug(f"Skipping URL (no match): {href}")
                continue
            full_url = BASE_URL + href
            urls.add(full_url)
        logging.info(f"Found {len(urls)} article URLs.")
        return list(urls)
    except Exception as e:
        logging.error(f"Failed to fetch URLs: {e}")
        return []

def get_article_info(url):
    """
    Scrapes the headline and publication timestamp from an article page.
    """
    try:
        time.sleep(random.uniform(1.5, 3.5))
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True, args=["--no-sandbox"])
            page = browser.new_page()
            page.goto(url, timeout=30000, wait_until="domcontentloaded")
            page.wait_for_timeout(3000)
            html = page.content()
            browser.close()

        soup = BeautifulSoup(html, 'lxml')
        headline_tag = soup.find('h1')
        headline = headline_tag.get_text(strip=True) if headline_tag else None

        time_tag = soup.find('time')
        published = (
            datetime.fromisoformat(time_tag['datetime'].replace('Z', '+00:00')).astimezone(timezone.utc)
            if time_tag and time_tag.has_attr('datetime') else None
        )
        return headline, published
    except Exception as e:
        logging.warning(f"Failed to extract info for {url}: {e}")
        return None, None

def load_posted_urls(path):
    """
    Loads a set of posted article IDs from a file.
    """
    if not os.path.exists(path):
        return set()
    with open(path, 'r') as f:
        return set(line.strip() for line in f if line.strip())

def save_posted_url(path, url):
    """
    Saves a normalized article ID to the posted URLs file.
    This should only be called after a successful post.
    """
    article_id = normalize_url(url)
    with open(path, 'a') as f:
        f.write(f"{article_id}\n")
        f.flush()
        os.fsync(f.fileno())
    logging.info(f"Saved posted ID to {path}: {article_id}")

def deduplicate_posted_urls(path):
    """
    Removes duplicate article IDs from the posted URLs file.
    """
    if not os.path.exists(path):
        return
    with open(path, 'r') as f:
        ids = set(line.strip() for line in f if line.strip())
    with open(path, 'w') as f:
        for id in sorted(ids):
            f.write(f"{id}\n")
