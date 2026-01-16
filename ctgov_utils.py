"""
CT.gov API helpers for safe query encoding, pagination, and extraction.
"""

from __future__ import annotations

from typing import Dict, Iterable, Optional, Set, Tuple
from urllib.parse import parse_qsl
import threading

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from ctgov_config import CTGOV_API, DEFAULT_PAGE_SIZE, DEFAULT_USER_AGENT

DEFAULT_RETRY_TOTAL = 3
DEFAULT_RETRY_BACKOFF = 0.5
DEFAULT_RETRY_STATUSES = (429, 500, 502, 503, 504)

_thread_local = threading.local()


def _configure_session(session: requests.Session) -> None:
    if getattr(session, "_ctgov_configured", False):
        return
    retry = Retry(
        total=DEFAULT_RETRY_TOTAL,
        backoff_factor=DEFAULT_RETRY_BACKOFF,
        status_forcelist=DEFAULT_RETRY_STATUSES,
        allowed_methods=("GET", "HEAD", "OPTIONS"),
        raise_on_status=False,
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    session._ctgov_configured = True


def get_session(
    user_agent: str = DEFAULT_USER_AGENT, accept: str = "application/json"
) -> requests.Session:
    """Return a thread-local requests session with consistent headers."""
    session = getattr(_thread_local, "session", None)
    if session is None:
        session = requests.Session()
        _thread_local.session = session
    _configure_session(session)
    session.headers.update({"User-Agent": user_agent, "Accept": accept})
    return session


def build_params(query: str) -> Dict[str, str]:
    """Parse a query string into a params dict without assuming prior encoding."""
    if not query:
        return {}
    cleaned = query.lstrip("?")
    return dict(parse_qsl(cleaned, keep_blank_values=True))


def extract_nct_ids(studies: Iterable[dict]) -> Set[str]:
    """Extract NCT IDs from CT.gov study records."""
    ncts: Set[str] = set()
    for study in studies or []:
        if not isinstance(study, dict):
            continue
        nct = (
            study.get("protocolSection", {})
            .get("identificationModule", {})
            .get("nctId", "")
        )
        if nct:
            ncts.add(nct.upper())
    return ncts


def iter_study_pages(
    session: requests.Session,
    params: Dict[str, str],
    timeout: int = 30,
    page_size: int = DEFAULT_PAGE_SIZE,
    max_pages: Optional[int] = None,
) -> Iterable[dict]:
    """Yield paginated CT.gov API responses for a query."""
    request_params = {k: v for k, v in params.items() if v is not None}
    request_params.setdefault("pageSize", page_size)
    request_params.setdefault("countTotal", "true")

    pages = 0
    while True:
        response = session.get(
            CTGOV_API, params=dict(request_params), timeout=timeout
        )
        response.raise_for_status()
        data = response.json()
        yield data

        pages += 1
        if max_pages and pages >= max_pages:
            break

        token = data.get("nextPageToken")
        if not token:
            break
        request_params["pageToken"] = token
        request_params.pop("countTotal", None)


def fetch_nct_ids(
    session: requests.Session,
    params: Dict[str, str],
    timeout: int = 30,
    page_size: int = DEFAULT_PAGE_SIZE,
    max_pages: Optional[int] = None,
) -> Tuple[Set[str], int]:
    """Fetch all NCT IDs for a query, returning (nct_ids, total_count)."""
    ncts: Set[str] = set()
    total_count = 0

    for idx, data in enumerate(
        iter_study_pages(
            session, params, timeout=timeout, page_size=page_size, max_pages=max_pages
        )
    ):
        if idx == 0:
            total_count = data.get("totalCount", 0)
        ncts.update(extract_nct_ids(data.get("studies", [])))

    return ncts, total_count


def fetch_total_count(
    session: requests.Session,
    params: Dict[str, str],
    timeout: int = 30,
) -> int:
    """Fetch only totalCount for a query without paging through results."""
    request_params = {k: v for k, v in params.items() if v is not None}
    request_params["countTotal"] = "true"
    request_params["pageSize"] = 1

    response = session.get(CTGOV_API, params=request_params, timeout=timeout)
    response.raise_for_status()
    return response.json().get("totalCount", 0)


def fetch_matching_nct_ids(
    session: requests.Session,
    params: Dict[str, str],
    nct_ids: Iterable[str],
    timeout: int = 30,
    batch_size: int = 100,
) -> Set[str]:
    """Fetch matching NCT IDs by combining query params with query.id batches."""
    ncts: Set[str] = set()
    nct_list = [n.strip().upper() for n in nct_ids if n]

    for start in range(0, len(nct_list), batch_size):
        batch = nct_list[start : start + batch_size]
        if not batch:
            continue
        batch_params = dict(params)
        batch_params["query.id"] = " OR ".join(batch)
        batch_found, _ = fetch_nct_ids(
            session, batch_params, timeout=timeout, page_size=max(100, len(batch))
        )
        ncts.update(batch_found)

    return ncts


def fetch_studies(
    session: requests.Session,
    params: Dict[str, str],
    timeout: int = 30,
    page_size: int = DEFAULT_PAGE_SIZE,
    max_pages: Optional[int] = None,
) -> Tuple[list, int]:
    """Fetch all studies for a query, returning (studies, total_count)."""
    studies = []
    total_count = 0

    for idx, data in enumerate(
        iter_study_pages(
            session, params, timeout=timeout, page_size=page_size, max_pages=max_pages
        )
    ):
        if idx == 0:
            total_count = data.get("totalCount", 0)
        studies.extend(data.get("studies", []))

    return studies, total_count
