# herald_bot.py

import os
import logging
import re
import time
import random
from bs4 import BeautifulSoup
import tweepy
from datetime import datetime, timezone
from dotenv import load_dotenv
import pytz
from playwright.sync_api import sync_playwright

# Load environment variables from .env
load_dotenv()

# Logging configuration
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("herald_bot.log"),
        logging.StreamHandler()
    ]
)

def normalize_url(url):
    return url.strip().split('?')[0].rstrip('/').lower()

class HeraldBot:
    BASE_URL = "https://www.heraldscotland.com"
    POLITICS_URL = f"{BASE_URL}/politics/"
    POSTED_URLS_FILE = "posted_urls_twitter.txt"

    def __init__(self):
        self.client = tweepy.Client(
            consumer_key=os.getenv("TWITTER_API_KEY"),
            consumer_secret=os.getenv("TWITTER_API_SECRET"),
            access_token=os.getenv("TWITTER_ACCESS_TOKEN"),
            access_token_secret=os.getenv("TWITTER_ACCESS_SECRET")
        )

    def load_posted_urls(self):
        if not os.path.exists(self.POSTED_URLS_FILE):
            return set()
        with open(self.POSTED_URLS_FILE, 'r') as f:
            return set(normalize_url(line) for line in f if line.strip())

    def save_posted_url(self, url):
        norm_url = normalize_url(url)
        with open(self.POSTED_URLS_FILE, 'a') as f:
            f.write(f"{norm_url}\n")
            f.flush()
            os.fsync(f.fileno())
        logging.info(f"Saved posted URL: {norm_url}")

    def deduplicate_posted_urls(self):
        if not os.path.exists(self.POSTED_URLS_FILE):
            return
        with open(self.POSTED_URLS_FILE, 'r') as f:
            urls = set(normalize_url(line) for line in f if line.strip())
        with open(self.POSTED_URLS_FILE, 'w') as f:
            for url in sorted(urls):
                f.write(f"{url}\n")

    def fetch_article_urls(self):
        try:
            time.sleep(random.uniform(1.5, 3.5))
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                page = browser.new_page()
                page.goto(self.POLITICS_URL, timeout=30000)
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
                full_url = normalize_url(self.BASE_URL + href)
                urls.add(full_url)
            logging.info(f"Found {len(urls)} article URLs.")
            return list(urls)
        except Exception as e:
            logging.error(f"Failed to fetch article URLs: {e}")
            return []

    def get_article_info(self, url):
        try:
            time.sleep(random.uniform(1.5, 3.5))
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                page = browser.new_page()
                page.goto(url, timeout=30000)
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

    def post_tweet(self, headline, url):
        text = f"{headline} {url}"[:280]
        try:
            self.client.create_tweet(text=text)
            self.save_posted_url(url)
            logging.info(f"Posted to X: {text}")
            return True
        except Exception as e:
            logging.error(f"Failed to post to X: {e}")
            return False

    def run(self):
        logging.info("Starting Herald bot run...")

        bst = pytz.timezone('Europe/London')
        now = datetime.now(timezone.utc).astimezone(bst)
        if not (7 <= now.hour < 20):
            logging.info("Outside 7 AM–8 PM BST. Skipping run.")
            return

        posted_urls = self.load_posted_urls()
        logging.info(f"Loaded {len(posted_urls)} previously posted URLs.")

        for url in self.fetch_article_urls():
            norm_url = normalize_url(url)
            if norm_url in posted_urls:
                logging.info(f"Already posted: {url}")
                continue
            headline, published = self.get_article_info(url)
            if not headline or not published:
                continue
            if (datetime.now(timezone.utc) - published).total_seconds() > 43200:
                logging.info(f"Too old to post: {url}")
                continue
            if self.post_tweet(headline, url):
                break  # Post only one per run

        self.deduplicate_posted_urls()
        logging.info("Herald bot finished run.")

if __name__ == "__main__":
    print("Running Herald Bot...")
    bot = HeraldBot()
    bot.run()
    print("Done!")
