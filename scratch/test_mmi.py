import requests
import json
from bs4 import BeautifulSoup

def main():
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    url = "https://www.tickertape.in/market-mood-index"
    try:
        print(f"Fetching {url}...")
        r = requests.get(url, headers=headers, timeout=10)
        print(f"Status Code: {r.status_code}")
        
        soup = BeautifulSoup(r.text, "html.parser")
        script = soup.find("script", id="__NEXT_DATA__")
        if not script:
            print("Could not find __NEXT_DATA__ script tag.")
            # Print a snippet of HTML to debug
            print(r.text[:500])
            return
            
        print("Parsing __NEXT_DATA__ script...")
        data = json.loads(script.string)
        
        # Dump keys to see the structure
        print("Root keys:", list(data.keys()))
        
        # Let's inspect props and search recursively for the MMI score
        props = data.get("props", {})
        page_props = props.get("pageProps", {})
        print("Page props keys:", list(page_props.keys()))
        
        # Often the score is under pageProps['mmiInfo'] or similar
        mmi_info = page_props.get("mmiInfo", {})
        print("mmiInfo:", mmi_info)
        
        # Let's search recursively for keys containing "score" or "mmi"
        def recursive_search(obj, path=""):
            results = []
            if isinstance(obj, dict):
                for k, v in obj.items():
                    current_path = f"{path}.{k}" if path else k
                    if "mmi" in k.lower() or "score" in k.lower() or k == "currentValue":
                        results.append((current_path, v))
                    results.extend(recursive_search(v, current_path))
            elif isinstance(obj, list):
                for idx, item in enumerate(obj):
                    current_path = f"{path}[{idx}]"
                    results.extend(recursive_search(item, current_path))
            return results

        found = recursive_search(data)
        print("\nRecursively found interesting fields:")
        for path, val in found:
            print(f"  {path}: {val}")

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()
