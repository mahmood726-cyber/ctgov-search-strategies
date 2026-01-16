"""Shared configuration for CT.gov search tooling."""

from typing import Final

# API endpoint for ClinicalTrials.gov v2 API
CTGOV_API: Final[str] = "https://clinicaltrials.gov/api/v2/studies"

# Default timeout for HTTP requests in seconds
DEFAULT_TIMEOUT: Final[int] = 30

# Default page size for paginated API requests
DEFAULT_PAGE_SIZE: Final[int] = 1000

# Default rate limit delay between requests in seconds
DEFAULT_RATE_LIMIT: Final[float] = 0.3

# Default User-Agent header for HTTP requests
DEFAULT_USER_AGENT: Final[str] = "CTgov-Search-Strategy-Validator/2.1"
