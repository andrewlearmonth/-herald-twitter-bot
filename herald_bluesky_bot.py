import os
import logging
import re
import time
import random
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timezone
from dotenv import load_dotenv
import pytz
from playwright.sync_api import sync_playwright
from atproto import Client, models

# Load environment variables
load_dotenv()

# Logging config
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("herald_bluesky_bot.log"),
        logging.StreamHandler()
    ]
)

def normalize_url(url):
    return url.strip().split('?')[0].rstrip('/').lower()

class HeraldBlueskyBot:
    BASE_URL = "https://www.heraldscotland.com"
    POLITICS_URL = f"{BASE_URL}/politics/"
    OWN_POSTED_FILE = "posted_urls_bluesky.txt"

    def __init__(self):
        self.client = Client()
        handle = os.getenv("BLUESKY_HANDLE")
        password = os.getenv("BLUESKY_APP_PASSWORD")
        if not handle or not password:
            raise ValueError("Missing Bluesky credentials")
        logging.info(f"Logging in to Bluesky as {handle}")
        self.client.login(login=handle, password=password)

    def load_posted_urls(self):
        if not os.path.exists(self.OWN_POSTED_FILE):
            return set()
        with open(self.OWN_POSTED_FILE, 'r') as f:
            return set(normalize_url(line) for line in f)

    def save_posted_url(self, url):
        with open(self.OWN_POSTED_FILE, 'a') as f:
            f.write(f"{normalize_url(url)}\n")

    def fetch_article_urls(self):
        try:
            time.sleep(random.uniform(1.5, 3.5))
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True, args=["--no-sandbox"])
                page = browser.new_page()
                page.goto(self.POLITICS_URL, timeout=30000, wait_until="domcontentloaded")
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
            logging.error(f"Failed to fetch URLs: {e}")
            return []

    def get_article_info(self, url):
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

    def post_to_bluesky(self, headline, url):
        text = headline[:300]
        if len(text) > 300:
            headline = headline[:300 - len(url) - 1]
            text = f"{headline} {url}"

        try:
            response = requests.get(url, timeout=10)
            soup = BeautifulSoup(response.text, "lxml")

            og_title = soup.find("meta", property="og:title")
            og_description = soup.find("meta", property="og:description")
            og_image = soup.find("meta", property="og:image")

            title = og_title["content"] if og_title and og_title.get("content") else headline
            description = og_description["content"] if og_description and og_description.get("content") else ""
            image_url = og_image["content"] if og_image and og_image.get("content") else None

            external = models.AppBskyEmbedExternal.External(
                uri=url,
                title=title[:300],
                description=description[:1000],
            )

            if image_url:
                try:
                    image_response = requests.get(image_url, timeout=10)
                    image_data = image_response.content
                    blob = self.client.com.atproto.repo.upload_blob(image_data).blob
                    external.thumb = blob
                except Exception as e:
                    logging.warning(f"Failed to fetch or upload OG image: {e}")

            embed = models.AppBskyEmbedExternal.Main(external=external)

            self.client.send_post(text=text, embed=embed)
            logging.info(f"Posted to Bluesky: {url}")
            return True

        except Exception as e:
            logging.error(f"Failed to post to Bluesky: {e}")
            return False

    def run(self):
        logging.info("Starting Herald Bluesky bot run.")
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
            if self.post_to_bluesky(headline, url):
                self.save_posted_url(url)
                break  # post only one per run

        logging.info("Herald Bluesky bot finished run.")

if __name__ == "__main__":
    print("Running Herald Bluesky Bot...")
    bot = HeraldBlueskyBot()
    bot.run()
    print("Done!")
