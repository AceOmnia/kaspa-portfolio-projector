import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from typing import Optional

from src.data.constants import VERSION


_SESSION: Optional[requests.Session] = None


def get_http_session() -> requests.Session:
    global _SESSION
    if _SESSION is None:
        session = requests.Session()
        retry = Retry(
            total=3,
            backoff_factor=0.5,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["GET"],
            raise_on_status=False,
        )
        adapter = HTTPAdapter(max_retries=retry)
        session.mount("https://", adapter)
        session.mount("http://", adapter)
        session.headers.update({
            "User-Agent": f"Kaspa-Portfolio-Projector/{VERSION} (+https://www.kaspa.org)",
            "Accept": "application/json",
        })
        _SESSION = session
    return _SESSION


