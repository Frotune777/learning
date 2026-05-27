import time

import requests

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
    "Connection": "keep-alive",
    "Referer": "https://www.nseindia.com/",
}

session = requests.Session()
session.headers.update(headers)


def test_html():
    try:
        print("Warming up cookies...")
        session.get("https://www.nseindia.com", timeout=15)
        time.sleep(1.0)

        url = "https://www.nseindia.com/get-quotes/equity?symbol=TCS"
        print("Fetching HTML from get-quotes/equity?symbol=TCS...")
        resp = session.get(url, timeout=15)
        print("Status:", resp.status_code)
        if resp.status_code == 200:
            html = resp.text
            print("Length of HTML:", len(html))

            # Check if TCS token "11536" is in the HTML!
            if "11536" in html:
                print("SUCCESS! TCS token 11536 found in HTML!")
                # Find some context lines around it
                lines = html.splitlines()
                for i, line in enumerate(lines):
                    if "11536" in line:
                        print(f"Line {i}: {line[:300]}")
            else:
                print("TCS token 11536 not found in HTML.")
        else:
            print("Failed:", resp.status_code)
    except Exception as e:
        print("Error:", e)


test_html()
