# ---------------------------------------------------------------------------------------
#           Extract Market Mood Index from TickerTape.in website
#
# Usage: Educational Purposes & training use only. Not for commercial redistribution.
# FabTrader Algorithmic Trading - Tutorials
# ---------------------------------------------------------------------------------------

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager

# Setup Chrome Options
chrome_options = Options()
chrome_options.add_argument("--headless")  # Run in background

# Initialize WebDriver
service = Service(ChromeDriverManager().install())
driver = webdriver.Chrome(service=service, options=chrome_options)

# Open TickerTape MMI Page
url = "https://www.tickertape.in/market-mood-index"
driver.get(url)

# Wait for page to load
driver.implicitly_wait(5)

# Locate MMI Score Element (Inspect the page to get correct XPath or CSS Selector)
mmi_score_element = driver.find_element(
    "xpath", "//span[contains(@class, 'jsx-3654585993 ')]"
)

# Extract Text
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
print("Market Mood Index by TickerTape")
print(f"MMI Score: {mmi_score} - Market Mood: {mmi_mood}")

# Close Browser
driver.quit()
