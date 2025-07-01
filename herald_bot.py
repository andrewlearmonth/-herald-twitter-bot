# herald_bot.py

import os
import logging
from dotenv import load_dotenv
from datetime import datetime, timezone
import pytz
import requests
from bs4 import BeautifulSoup
import tweepy
from atproto import Client, models

from herald_shared import (
    fetch_article_urls,
    get_article_info,
    normalize_url,
    load_posted_urls,
    save_posted_url,
    deduplicate_posted_urls
)

# Load environment variables
load_dotenv()

# Logging setup
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("herald_bot.log"),
        logging.StreamHandler()
    ]
)

# File paths
TWITTER_FILE = "posted_urls_twitter.txt"
BLUESKY_FILE = "posted_urls_bluesky.txt"

# Posting time limits (7am–8pm UK)
def within_posting_hours():
    bst = pytz.timezone("Europe/London")
    now = datetime.now(timezone.utc).astimezone(bst)
    return 7 <= now.hour < 20

# Twitter posting
def post_to_twitter(headline, url):
    try:
        client = tweepy.Client(
            consumer_key=os.getenv("TWITTER_API_KEY"),
            consumer_secret=os.getenv("TWITTER_API_SECRET"),
            access_token=os.getenv("TWITTER_ACCESS_TOKEN"),
            access_token_secret=os.getenv("TWITTER_ACCESS_SECRET")
        )
        text = f"{headline} {url}"[:280]
        client.create_tweet(text=text)
        logging.info(f"Posted to Twitter: {url}")
        return True
    except Exception as e:
        logging.error(f"Failed to post to Twitter: {e}")
        return False

# Bluesky posting
def post_to_bluesky(headline, url):
    try:
        client = Client()
        handle = os.getenv("BLUESKY_HANDLE")
        password = os.getenv("BLUESKY_APP_PASSWORD")
        client.login(handle, password)

        # Fetch OG data
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
                img = requests.get(image_url, timeout=10)
                blob = client.com.atproto.repo.upload_blob(img.content).blob
                external.thumb = blob
            except Exception as e:
                logging.warning(f"Failed to upload image to Bluesky: {e}")

        embed = models.AppBskyEmbedExternal.Main(external=external)
        client.send_post(text=headline[:300], embed=embed)
        logging.info(f"Posted to Bluesky: {url}")
        return True
    except Exception as e:
        logging.error(f"Failed to post to Bluesky: {e}")
        return False

# Main bot logic
def run():
    logging.info("Starting Herald merged bot run...")
    if not within_posting_hours():
        logging.info("Outside 7am–8pm UK time. Skipping.")
        return

    twitter_urls = load_posted_urls(TWITTER_FILE)
    bluesky_urls = load_posted_urls(BLUESKY_FILE)

    all_posted = twitter_urls.union(bluesky_urls)

    for url in fetch_article_urls():
        norm_url = normalize_url(url)
        if norm_url in all_posted:
            logging.info(f"Already posted: {url}")
            continue

        headline, published = get_article_info(url)
        if not headline or not published:
            continue

        age_seconds = (datetime.now(timezone.utc) - published).total_seconds()
        if age_seconds > 43200:
            logging.info(f"Too old to post: {url}")
            continue

        posted_anywhere = False

        if post_to_twitter(headline, url):
            save_posted_url(TWITTER_FILE, url)
            posted_anywhere = True

        if post_to_bluesky(headline, url):
            save_posted_url(BLUESKY_FILE, url)
            posted_anywhere = True

        if posted_anywhere:
            break  # Post only one article per run

    deduplicate_posted_urls(TWITTER_FILE)
    deduplicate_posted_urls(BLUESKY_FILE)
    logging.info("Herald merged bot finished run.")

if __name__ == "__main__":
    print("Running Herald Bot...")
    run()
    print("Done!")
