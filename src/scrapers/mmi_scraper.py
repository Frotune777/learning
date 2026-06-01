"""
File: src/nse_bhavcopy/mmi_scraper.py
Purpose: Scrapes Market Mood Index (MMI) from Tickertape using HTTP/Next.js data with Selenium fallback.
Last Modified: 2026-06-01
"""

import json
import requests
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager


def fetch_mmi_score() -> tuple[float, str]:
    """
    Fetches the latest Market Mood Index from Tickertape.
    Tries highly efficient direct Next.js static JSON extraction first,
    falling back to Selenium if Next.js format changes.

    Returns:
        Tuple[float, str]: The MMI score and the corresponding mood category string.
        Returns (0.0, "Unknown") on failure.
    """
    url = "https://www.tickertape.in/market-mood-index"
    
    # ----------------------------------------------------
    # Method 1: Lightweight HTTP requests + __NEXT_DATA__
    # ----------------------------------------------------
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
        resp = requests.get(url, headers=headers, timeout=10)
        if resp.status_code == 200:
            soup = BeautifulSoup(resp.text, "html.parser")
            script = soup.find("script", id="__NEXT_DATA__")
            if script:
                data = json.loads(script.string)
                mmi_val = data.get("props", {}).get("pageProps", {}).get("nowData", {}).get("currentValue")
                if mmi_val is not None:
                    mmi_score = float(mmi_val)
                    if mmi_score >= 70:
                        mmi_mood = "Extreme Greed"
                    elif mmi_score >= 50:
                        mmi_mood = "Greed"
                    elif mmi_score >= 30:
                        mmi_mood = "Fear"
                    else:
                        mmi_mood = "Extreme Fear"
                    return mmi_score, mmi_mood
    except Exception as exc:
        print(f"Direct HTTP fetch failed: {exc}. Retrying with Selenium...")

    # ----------------------------------------------------
    # Method 2: Headless Selenium Fallback
    # ----------------------------------------------------
    driver = None
    try:
        print("  Falling back to headless Selenium...")
        # Setup Chrome Options
        chrome_options = Options()
        chrome_options.add_argument("--headless")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")

        # Initialize WebDriver
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=chrome_options)

        # Open TickerTape MMI Page
        driver.get(url)

        # Wait for page to load
        driver.implicitly_wait(10)

        # Locate MMI Score Element
        mmi_score_element = driver.find_element(
            "xpath", "//span[contains(@class, 'jsx-3654585993')]"
        )

        mmi_score = float(mmi_score_element.text)

        # Extract Market Mood
        if mmi_score >= 70:
            mmi_mood = "Extreme Greed"
        elif mmi_score >= 50:
            mmi_mood = "Greed"
        elif mmi_score >= 30:
            mmi_mood = "Fear"
        else:
            mmi_mood = "Extreme Fear"

        return mmi_score, mmi_mood

    except Exception as e:
        print(f"Failed to fetch MMI Score from Tickertape: {e}")
        return 0.0, "Unknown"

    finally:
        if driver:
            driver.quit()


def run_mmi_cli() -> None:
    """
    CLI wrapper to fetch and print the MMI score.
    """
    print("  Initializing Selenium WebDriver (headless)...")
    score, mood = fetch_mmi_score()

    if score == 0.0:
        print("  Could not fetch the Market Mood Index.")
        return

    print("\n  Market Mood Index (by TickerTape)")
    print(f"  Score: {score:.2f} — Mood: {mood}\n")
