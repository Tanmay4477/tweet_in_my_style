from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from webdriver_manager.chrome import ChromeDriverManager
import time
import json
import argparse
import re
from datetime import datetime

def scrape_user_tweets(username, limit=50, output_file=None, headless=True):
    """
    Scrape tweets from a Twitter/X user using Selenium
    
    Args:
        username (str): Twitter username (without the @ symbol)
        limit (int): Maximum number of tweets to collect (default: 50)
        output_file (str, optional): Path to save the JSON file
        headless (bool): Run browser in headless mode (default: True)
    
    Returns:
        list: List of tweet dictionaries
    """
    if not output_file:
        output_file = f"{username}_tweets.json"
    
    # Set up Chrome options
    chrome_options = Options()
    if headless:
        chrome_options.add_argument("--headless")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--window-size=1920,1080")
    chrome_options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/98.0.4758.102 Safari/537.36")
    
    # Set up driver
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)
    
    # Go to user's timeline
    url = f"https://twitter.com/{username}"
    print(f"Opening {url}")
    driver.get(url)
    
    # Wait for timeline to load
    try:
        WebDriverWait(driver, 20).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "article[data-testid='tweet']"))
        )
    except TimeoutException:
        print("Timeout waiting for page to load. User may not exist or Twitter might be blocking the scraper.")
        driver.quit()
        return []
    
    # Initialize tweet list
    tweets_list = []
    last_height = driver.execute_script("return document.body.scrollHeight")
    
    print(f"Starting to scrape tweets from @{username}...")
    
    while len(tweets_list) < limit:
        # Extract tweets
        articles = driver.find_elements(By.CSS_SELECTOR, "article[data-testid='tweet']")
        new_tweets = 0
        
        for article in articles:
            try:
                # Extract tweet data
                tweet_id = None
                links = article.find_elements(By.CSS_SELECTOR, "a[href*='/status/']")
                for link in links:
                    href = link.get_attribute("href")
                    if "/status/" in href:
                        tweet_id = href.split("/status/")[1].split("?")[0]
                        break
                
                # Skip if we've already processed this tweet
                if tweet_id and any(t["id"] == tweet_id for t in tweets_list):
                    continue
                
                # Get tweet text
                try:
                    content_elem = article.find_element(By.CSS_SELECTOR, "div[data-testid='tweetText']")
                    content = content_elem.text
                except NoSuchElementException:
                    content = ""
                
                # Get timestamp
                try:
                    time_elem = article.find_element(By.CSS_SELECTOR, "time")
                    timestamp = time_elem.get_attribute("datetime")
                    date_str = datetime.fromisoformat(timestamp.replace("Z", "+00:00")).strftime("%Y-%m-%d %H:%M:%S")
                except (NoSuchElementException, ValueError):
                    date_str = None
                
                # Get engagement stats
                stats = {
                    "replyCount": 0,
                    "retweetCount": 0,
                    "likeCount": 0
                }
                
                try:
                    stats_elements = article.find_elements(By.CSS_SELECTOR, "div[data-testid$='-count']")
                    for stat in stats_elements:
                        stat_id = stat.get_attribute("data-testid")
                        if "reply-count" in stat_id:
                            stats["replyCount"] = _parse_count(stat.text)
                        elif "retweet-count" in stat_id:
                            stats["retweetCount"] = _parse_count(stat.text)
                        elif "like-count" in stat_id:
                            stats["likeCount"] = _parse_count(stat.text)
                except NoSuchElementException:
                    pass
                
                # Check for media
                has_media = False
                try:
                    media_elements = article.find_elements(By.CSS_SELECTOR, "div[data-testid='tweetPhoto'], div[data-testid='videoPlayer']")
                    has_media = len(media_elements) > 0
                except NoSuchElementException:
                    pass
                
                # Get hashtags
                hashtags = []
                if content:
                    hashtags = re.findall(r'#(\w+)', content)
                
                # Get mentions
                mentions = []
                if content:
                    mentions = re.findall(r'@(\w+)', content)
                
                # Create tweet dictionary
                if tweet_id:  # Only add if we found an ID
                    tweet_dict = {
                        "id": tweet_id,
                        "date": date_str,
                        "content": content,
                        "url": f"https://twitter.com/{username}/status/{tweet_id}",
                        "replyCount": stats["replyCount"],
                        "retweetCount": stats["retweetCount"],
                        "likeCount": stats["likeCount"],
                        "hashtags": hashtags,
                        "mentionedUsers": mentions,
                        "has_media": has_media
                    }
                    
                    tweets_list.append(tweet_dict)
                    new_tweets += 1
                    
                    if len(tweets_list) % 10 == 0:
                        print(f"Scraped {len(tweets_list)} tweets so far...")
                    
                    if len(tweets_list) >= limit:
                        break
            
            except Exception as e:
                print(f"Error processing tweet: {e}")
                continue
        
        if len(tweets_list) >= limit:
            break
        
        # Scroll down to load more tweets
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(2)  # Wait for new tweets to load
        
        # Check if we've reached the end of the timeline
        new_height = driver.execute_script("return document.body.scrollHeight")
        if new_height == last_height and new_tweets == 0:
            print("Reached the end of the timeline or no new tweets loaded.")
            break
        
        last_height = new_height
    
    driver.quit()
    
    # Save to JSON file
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(tweets_list, f, ensure_ascii=False, indent=4)
    
    print(f"Finished scraping. Total tweets collected: {len(tweets_list)}")
    print(f"Data saved to {output_file}")
    
    return tweets_list

def _parse_count(count_str):
    """Parse count strings like '1.2K' into integers"""
    if not count_str:
        return 0
    
    count_str = count_str.strip().upper()
    
    if 'K' in count_str:
        return int(float(count_str.replace('K', '')) * 1000)
    elif 'M' in count_str:
        return int(float(count_str.replace('M', '')) * 1000000)
    else:
        try:
            return int(count_str)
        except ValueError:
            return 0

if __name__ == "__main__":
    # Set up command line arguments
    parser = argparse.ArgumentParser(description='Scrape tweets from a Twitter/X user using Selenium')
    parser.add_argument('username', type=str, help='Twitter username (without @)')
    parser.add_argument('--limit', type=int, default=50, help='Maximum number of tweets to collect')
    parser.add_argument('--output', type=str, default=None, help='Output JSON file path')
    parser.add_argument('--visible', action='store_true', help='Run browser in visible mode (not headless)')
    
    args = parser.parse_args()
    
    # Run the scraper
    scrape_user_tweets(args.username, args.limit, args.output, not args.visible)