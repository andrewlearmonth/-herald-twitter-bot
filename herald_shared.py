# herald_shared.py

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
    return url.strip().split('?')[0].rstrip('/').lower()

def fetch_article_urls():
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
            if not re.search(r'/\d{8,}\.', href):
                continue
            full_url = normalize_url(BASE_URL + href)
            urls.add(full_url)
        logging.info(f"Found {len(urls)} article URLs.")
        return list(urls)
    except Exception as e:
        logging.error(f"Failed to fetch URLs: {e}")
        return []

def get_article_info(url):
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
        headline = soup.find('h1').get_text(strip=True) if soup.find('h1') else None
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
    if not os.path.exists(path):
        return set()
    with open(path, 'r') as f:
        return set(normalize_url(line) for line in f if line.strip())

def save_posted_url(path, url):
    norm_url = normalize_url(url)
    with open(path, 'a') as f:
        f.write(f"{norm_url}\n")
        f.flush()
        os.fsync(f.fileno())
    logging.info(f"Saved posted URL to {path}: {norm_url}")

def deduplicate_posted_urls(path):
    if not os.path.exists(path):
        return
    with open(path, 'r') as f:
        urls = set(normalize_url(line) for line in f if line.strip())
    with open(path, 'w') as f:
        for url in sorted(urls):
            f.write(f"{url}\n")
