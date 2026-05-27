import json
import logging

from src.data.fetcher.session.manager import SessionManager
from src.data.fetcher.session.nse_session import NSESessionInitializer

logging.basicConfig(level=logging.INFO)
LOGGER = logging.getLogger("test_masters")


def test_fetch_masters():
    sm = SessionManager(rate_limit_delay=0.1)
    init = NSESessionInitializer(sm)

    LOGGER.info("Warming up cookies using NSESessionInitializer...")
    init.ensure_initialized()

    session = sm.get_session()
    url = "https://charting.nseindia.com/Charts/GetEQMasters"
    headers = {
        "Accept": "application/json, text/javascript, */*; q=0.01",
        "Referer": "https://charting.nseindia.com/",
        "X-Requested-With": "XMLHttpRequest",
    }

    LOGGER.info("Sending request to GetEQMasters with active session cookies...")
    try:
        resp = session.get(url, headers=headers, timeout=30)
        LOGGER.info("Status Code: %d", resp.status_code)
        if resp.status_code == 200:
            LOGGER.info("SUCCESS!")
            text = resp.text
            LOGGER.info("Response length: %d", len(text))
            try:
                data = resp.json()
                LOGGER.info("Data type: %s", type(data))
                if isinstance(data, list) and len(data) > 0:
                    LOGGER.info("Found %d records!", len(data))
                    LOGGER.info("First 3 records:")
                    LOGGER.info(json.dumps(data[:3], indent=2))
            except Exception as json_err:
                LOGGER.error("Failed to parse JSON: %s", json_err)
                LOGGER.info("First 500 chars of response: %s", text[:500])
        else:
            LOGGER.error("Failed to fetch. Response headers: %s", resp.headers)
            LOGGER.error("Response text snippet: %s", resp.text[:500])
    except Exception as e:
        LOGGER.error("Request failed: %s", e)


if __name__ == "__main__":
    test_fetch_masters()
