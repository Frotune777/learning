"""
File: src/nse_bhavcopy/mmi_scraper.py
Purpose: Scrapes Market Mood Index (MMI) from Tickertape using Selenium.
Last Modified: 2026-05-27
"""

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager


def fetch_mmi_score() -> tuple[float, str]:
    """
    Fetches the latest Market Mood Index from Tickertape via Selenium.

    Returns:
        Tuple[float, str]: The MMI score and the corresponding mood category string.
        Returns (0.0, "Unknown") on failure.

    Raises:
        Exception: If Selenium fails to start or locate the element.
    """
    driver = None
    try:
        # Setup Chrome Options
        chrome_options = Options()
        chrome_options.add_argument("--headless")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")

        # Initialize WebDriver
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=chrome_options)

        # Open TickerTape MMI Page
        url = "https://www.tickertape.in/market-mood-index"
        driver.get(url)

        # Wait for page to load
        driver.implicitly_wait(10)

        # Locate MMI Score Element
        # The class 'jsx-3654585993 ' was provided in the prototype.
        # Using a safer approach with broader contains criteria if possible,
        # but sticking to the prototype's logic for now.
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
