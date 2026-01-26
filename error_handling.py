#!/usr/bin/env python3
"""
Robust Error Handling Module for CT.gov Search Strategies

Provides comprehensive error handling utilities including:
- Retry logic with exponential backoff
- Circuit breaker pattern for API failures
- Comprehensive error codes and user-friendly messages
- Error logging with timestamps
- Rate limiting protection

Based on best practices for handling unreliable external APIs.

Example:
    >>> from error_handling import with_retry, CircuitBreaker, CTGovError
    >>>
    >>> # Use decorator for automatic retry
    >>> @with_retry(max_retries=3, backoff_factor=2)
    ... def fetch_data():
    ...     response = requests.get(url)
    ...     response.raise_for_status()
    ...     return response.json()
    >>>
    >>> # Use circuit breaker for failing services
    >>> breaker = CircuitBreaker(failure_threshold=5, reset_timeout=60)
    >>> result = breaker.call(fetch_data)
"""

from __future__ import annotations

import functools
import logging
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum, auto
from typing import Any, Callable, Dict, Final, List, Optional, Tuple, TypeVar, Union

import requests

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Type variable for generic functions
T = TypeVar('T')

# Default retry configuration
DEFAULT_MAX_RETRIES: Final[int] = 3
DEFAULT_RETRY_DELAYS: Final[Tuple[float, ...]] = (1.0, 2.0, 4.0)  # Exponential: 1s, 2s, 4s
DEFAULT_TIMEOUT: Final[int] = 30


class ErrorCode(Enum):
    """
    Comprehensive error codes for CT.gov search operations.

    Error codes are grouped by category:
    - 1xxx: Network/Connection errors
    - 2xxx: API/Response errors
    - 3xxx: Data/Validation errors
    - 4xxx: Rate limiting errors
    - 5xxx: Internal/System errors
    """
    # Network errors (1xxx)
    CONNECTION_ERROR = 1001
    TIMEOUT_ERROR = 1002
    DNS_ERROR = 1003
    SSL_ERROR = 1004
    PROXY_ERROR = 1005

    # API errors (2xxx)
    API_ERROR = 2001
    INVALID_RESPONSE = 2002
    EMPTY_RESPONSE = 2003
    MALFORMED_JSON = 2004
    API_VERSION_MISMATCH = 2005
    ENDPOINT_NOT_FOUND = 2006
    METHOD_NOT_ALLOWED = 2007
    SERVICE_UNAVAILABLE = 2008

    # Data errors (3xxx)
    INVALID_NCT_ID = 3001
    INVALID_CONDITION = 3002
    INVALID_STRATEGY = 3003
    VALIDATION_ERROR = 3004
    DATA_PARSE_ERROR = 3005

    # Rate limiting (4xxx)
    RATE_LIMITED = 4001
    QUOTA_EXCEEDED = 4002
    TOO_MANY_REQUESTS = 4003

    # System errors (5xxx)
    INTERNAL_ERROR = 5001
    CIRCUIT_OPEN = 5002
    MAX_RETRIES_EXCEEDED = 5003
    UNKNOWN_ERROR = 5999


# User-friendly error messages
ERROR_MESSAGES: Final[Dict[ErrorCode, str]] = {
    ErrorCode.CONNECTION_ERROR: "Unable to connect to the server. Please check your internet connection.",
    ErrorCode.TIMEOUT_ERROR: "The request timed out. The server may be busy. Please try again.",
    ErrorCode.DNS_ERROR: "Unable to resolve the server address. Please check your network settings.",
    ErrorCode.SSL_ERROR: "Secure connection failed. Please check your security settings.",
    ErrorCode.PROXY_ERROR: "Proxy connection failed. Please check your proxy settings.",

    ErrorCode.API_ERROR: "The API returned an error. Please try again later.",
    ErrorCode.INVALID_RESPONSE: "Received an invalid response from the server.",
    ErrorCode.EMPTY_RESPONSE: "The server returned no data for this search.",
    ErrorCode.MALFORMED_JSON: "The server response could not be parsed.",
    ErrorCode.API_VERSION_MISMATCH: "API version mismatch. Please update the application.",
    ErrorCode.ENDPOINT_NOT_FOUND: "The requested resource was not found.",
    ErrorCode.METHOD_NOT_ALLOWED: "The request method is not supported.",
    ErrorCode.SERVICE_UNAVAILABLE: "The service is temporarily unavailable. Please try again later.",

    ErrorCode.INVALID_NCT_ID: "The NCT ID format is invalid. Format should be NCT followed by 8 digits.",
    ErrorCode.INVALID_CONDITION: "The condition/disease name is invalid or empty.",
    ErrorCode.INVALID_STRATEGY: "Unknown search strategy. Valid strategies are S1-S10.",
    ErrorCode.VALIDATION_ERROR: "The input data failed validation.",
    ErrorCode.DATA_PARSE_ERROR: "Unable to parse the returned data.",

    ErrorCode.RATE_LIMITED: "Too many requests. Please wait before trying again.",
    ErrorCode.QUOTA_EXCEEDED: "API quota exceeded. Please try again later.",
    ErrorCode.TOO_MANY_REQUESTS: "Request rate limit reached. Slowing down requests.",

    ErrorCode.INTERNAL_ERROR: "An internal error occurred. Please report this issue.",
    ErrorCode.CIRCUIT_OPEN: "Service temporarily disabled due to repeated failures.",
    ErrorCode.MAX_RETRIES_EXCEEDED: "Maximum retry attempts reached. Please try again later.",
    ErrorCode.UNKNOWN_ERROR: "An unexpected error occurred. Please try again."
}


class CTGovError(Exception):
    """
    Base exception for CT.gov search errors.

    Provides structured error information with error codes,
    user-friendly messages, and debugging context.

    Attributes:
        code: ErrorCode enum value
        message: User-friendly error message
        details: Additional error context
        timestamp: When the error occurred
        original_exception: The underlying exception, if any
    """

    def __init__(
        self,
        code: ErrorCode,
        message: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        original_exception: Optional[Exception] = None
    ) -> None:
        self.code = code
        self.message = message or ERROR_MESSAGES.get(code, "Unknown error")
        self.details = details or {}
        self.timestamp = datetime.now().isoformat()
        self.original_exception = original_exception

        super().__init__(self.message)

        # Log the error
        logger.error(
            f"[{self.code.name}] {self.message}",
            extra={
                'error_code': self.code.value,
                'details': self.details,
                'timestamp': self.timestamp
            }
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert error to dictionary for JSON serialization."""
        return {
            'error_code': self.code.value,
            'error_name': self.code.name,
            'message': self.message,
            'details': self.details,
            'timestamp': self.timestamp
        }

    def __str__(self) -> str:
        return f"[{self.code.name}] {self.message}"

    def __repr__(self) -> str:
        return f"CTGovError({self.code.name}, '{self.message}')"


class NetworkError(CTGovError):
    """Network-related errors (connection, timeout, DNS, SSL)."""

    def __init__(
        self,
        code: ErrorCode = ErrorCode.CONNECTION_ERROR,
        **kwargs: Any
    ) -> None:
        super().__init__(code, **kwargs)


class APIError(CTGovError):
    """API-related errors (response, parsing, version)."""

    def __init__(
        self,
        code: ErrorCode = ErrorCode.API_ERROR,
        status_code: Optional[int] = None,
        **kwargs: Any
    ) -> None:
        if status_code:
            kwargs.setdefault('details', {})['status_code'] = status_code
        super().__init__(code, **kwargs)


class ValidationError(CTGovError):
    """Data validation errors."""

    def __init__(
        self,
        code: ErrorCode = ErrorCode.VALIDATION_ERROR,
        field: Optional[str] = None,
        **kwargs: Any
    ) -> None:
        if field:
            kwargs.setdefault('details', {})['field'] = field
        super().__init__(code, **kwargs)


class RateLimitError(CTGovError):
    """Rate limiting errors."""

    def __init__(
        self,
        code: ErrorCode = ErrorCode.RATE_LIMITED,
        retry_after: Optional[int] = None,
        **kwargs: Any
    ) -> None:
        if retry_after:
            kwargs.setdefault('details', {})['retry_after'] = retry_after
        super().__init__(code, **kwargs)


class CircuitBreakerError(CTGovError):
    """Circuit breaker open error."""

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(ErrorCode.CIRCUIT_OPEN, **kwargs)


class CircuitState(Enum):
    """Circuit breaker states."""
    CLOSED = auto()  # Normal operation
    OPEN = auto()    # Failing, reject requests
    HALF_OPEN = auto()  # Testing if service recovered


@dataclass
class CircuitBreaker:
    """
    Circuit breaker pattern implementation for API calls.

    Prevents cascading failures by temporarily disabling calls to
    a failing service. After a timeout, allows limited requests
    to test if the service has recovered.

    States:
    - CLOSED: Normal operation, requests pass through
    - OPEN: Service failing, requests rejected immediately
    - HALF_OPEN: Testing recovery, limited requests allowed

    Example:
        >>> breaker = CircuitBreaker(failure_threshold=5, reset_timeout=60)
        >>> try:
        ...     result = breaker.call(lambda: requests.get(url))
        ... except CircuitBreakerError:
        ...     print("Service unavailable")
    """
    failure_threshold: int = 5
    reset_timeout: int = 60  # seconds
    half_open_max_calls: int = 3

    _state: CircuitState = field(default=CircuitState.CLOSED, init=False)
    _failure_count: int = field(default=0, init=False)
    _last_failure_time: float = field(default=0.0, init=False)
    _half_open_calls: int = field(default=0, init=False)
    _lock: threading.Lock = field(default_factory=threading.Lock, init=False)

    @property
    def state(self) -> CircuitState:
        """Get current circuit state."""
        with self._lock:
            if self._state == CircuitState.OPEN:
                # Check if we should transition to half-open
                if time.time() - self._last_failure_time >= self.reset_timeout:
                    self._state = CircuitState.HALF_OPEN
                    self._half_open_calls = 0
                    logger.info("Circuit breaker transitioning to HALF_OPEN")
            return self._state

    def call(self, func: Callable[[], T]) -> T:
        """
        Execute function through circuit breaker.

        Args:
            func: Function to execute

        Returns:
            Result of function call

        Raises:
            CircuitBreakerError: If circuit is open
        """
        state = self.state

        if state == CircuitState.OPEN:
            raise CircuitBreakerError(
                message=f"Circuit breaker is OPEN. Will retry after {self.reset_timeout}s",
                details={'failure_count': self._failure_count}
            )

        try:
            result = func()
            self._on_success()
            return result
        except Exception as e:
            self._on_failure()
            raise

    def _on_success(self) -> None:
        """Handle successful call."""
        with self._lock:
            if self._state == CircuitState.HALF_OPEN:
                self._half_open_calls += 1
                if self._half_open_calls >= self.half_open_max_calls:
                    # Service recovered, close circuit
                    self._state = CircuitState.CLOSED
                    self._failure_count = 0
                    logger.info("Circuit breaker CLOSED - service recovered")
            elif self._state == CircuitState.CLOSED:
                # Reset failure count on success
                self._failure_count = 0

    def _on_failure(self) -> None:
        """Handle failed call."""
        with self._lock:
            self._failure_count += 1
            self._last_failure_time = time.time()

            if self._state == CircuitState.HALF_OPEN:
                # Failed during testing, open circuit again
                self._state = CircuitState.OPEN
                logger.warning("Circuit breaker OPEN - half-open test failed")
            elif self._failure_count >= self.failure_threshold:
                # Threshold reached, open circuit
                self._state = CircuitState.OPEN
                logger.warning(
                    f"Circuit breaker OPEN - threshold reached "
                    f"({self._failure_count} failures)"
                )

    def reset(self) -> None:
        """Manually reset the circuit breaker."""
        with self._lock:
            self._state = CircuitState.CLOSED
            self._failure_count = 0
            self._half_open_calls = 0
            logger.info("Circuit breaker manually reset")


def classify_exception(exc: Exception) -> CTGovError:
    """
    Classify an exception into the appropriate CTGovError type.

    Args:
        exc: The exception to classify

    Returns:
        CTGovError with appropriate error code
    """
    if isinstance(exc, CTGovError):
        return exc

    if isinstance(exc, requests.exceptions.ConnectionError):
        return NetworkError(
            code=ErrorCode.CONNECTION_ERROR,
            original_exception=exc,
            details={'exception_type': type(exc).__name__}
        )

    if isinstance(exc, requests.exceptions.Timeout):
        return NetworkError(
            code=ErrorCode.TIMEOUT_ERROR,
            original_exception=exc
        )

    if isinstance(exc, requests.exceptions.SSLError):
        return NetworkError(
            code=ErrorCode.SSL_ERROR,
            original_exception=exc
        )

    if isinstance(exc, requests.exceptions.ProxyError):
        return NetworkError(
            code=ErrorCode.PROXY_ERROR,
            original_exception=exc
        )

    if isinstance(exc, requests.exceptions.HTTPError):
        response = getattr(exc, 'response', None)
        status_code = response.status_code if response is not None else None

        if status_code == 429:
            retry_after = response.headers.get('Retry-After', 60) if response else 60
            return RateLimitError(
                retry_after=int(retry_after),
                original_exception=exc
            )
        elif status_code == 404:
            return APIError(
                code=ErrorCode.ENDPOINT_NOT_FOUND,
                status_code=status_code,
                original_exception=exc
            )
        elif status_code == 503:
            return APIError(
                code=ErrorCode.SERVICE_UNAVAILABLE,
                status_code=status_code,
                original_exception=exc
            )
        else:
            return APIError(
                code=ErrorCode.API_ERROR,
                status_code=status_code,
                original_exception=exc
            )

    if isinstance(exc, (ValueError, KeyError, TypeError)):
        return ValidationError(
            code=ErrorCode.DATA_PARSE_ERROR,
            original_exception=exc,
            details={'message': str(exc)}
        )

    # Unknown error
    return CTGovError(
        code=ErrorCode.UNKNOWN_ERROR,
        original_exception=exc,
        details={'exception_type': type(exc).__name__, 'message': str(exc)}
    )


def with_retry(
    max_retries: int = DEFAULT_MAX_RETRIES,
    retry_delays: Optional[Tuple[float, ...]] = None,
    retryable_errors: Optional[Tuple[type, ...]] = None,
    on_retry: Optional[Callable[[int, Exception], None]] = None
) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """
    Decorator for automatic retry with exponential backoff.

    Args:
        max_retries: Maximum number of retry attempts
        retry_delays: Tuple of delay times in seconds for each retry
        retryable_errors: Exception types that should trigger retry
        on_retry: Optional callback called on each retry (attempt, exception)

    Returns:
        Decorated function with retry logic

    Example:
        >>> @with_retry(max_retries=3, retry_delays=(1, 2, 4))
        ... def fetch_data(url):
        ...     response = requests.get(url, timeout=10)
        ...     response.raise_for_status()
        ...     return response.json()
    """
    if retry_delays is None:
        retry_delays = DEFAULT_RETRY_DELAYS

    if retryable_errors is None:
        retryable_errors = (
            requests.exceptions.ConnectionError,
            requests.exceptions.Timeout,
            requests.exceptions.HTTPError,
            NetworkError,
            APIError
        )

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> T:
            last_exception: Optional[Exception] = None

            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except retryable_errors as e:
                    last_exception = e

                    if attempt < max_retries:
                        delay = retry_delays[min(attempt, len(retry_delays) - 1)]

                        # Check for rate limiting with Retry-After header
                        if isinstance(e, RateLimitError):
                            delay = max(delay, e.details.get('retry_after', delay))

                        logger.warning(
                            f"Attempt {attempt + 1}/{max_retries + 1} failed: {e}. "
                            f"Retrying in {delay}s..."
                        )

                        if on_retry:
                            on_retry(attempt + 1, e)

                        time.sleep(delay)
                    else:
                        logger.error(
                            f"All {max_retries + 1} attempts failed for {func.__name__}"
                        )

            # All retries exhausted
            raise CTGovError(
                code=ErrorCode.MAX_RETRIES_EXCEEDED,
                message=f"Failed after {max_retries + 1} attempts",
                original_exception=last_exception,
                details={'function': func.__name__, 'max_retries': max_retries}
            )

        return wrapper
    return decorator


class RetryableSession:
    """
    HTTP session with built-in retry logic and error handling.

    Wraps requests.Session with automatic retries, circuit breaker,
    and comprehensive error classification.

    Example:
        >>> session = RetryableSession(max_retries=3)
        >>> data = session.get_json("https://api.example.com/data")
    """

    def __init__(
        self,
        max_retries: int = DEFAULT_MAX_RETRIES,
        retry_delays: Tuple[float, ...] = DEFAULT_RETRY_DELAYS,
        timeout: int = DEFAULT_TIMEOUT,
        circuit_breaker: Optional[CircuitBreaker] = None,
        user_agent: str = "CTGov-Search-Strategies/1.0"
    ) -> None:
        """
        Initialize retryable session.

        Args:
            max_retries: Maximum retry attempts per request
            retry_delays: Delay times for exponential backoff
            timeout: Request timeout in seconds
            circuit_breaker: Optional shared circuit breaker
            user_agent: User-Agent header value
        """
        self.max_retries = max_retries
        self.retry_delays = retry_delays
        self.timeout = timeout
        self.circuit_breaker = circuit_breaker
        self._session = requests.Session()
        self._session.headers.update({
            'User-Agent': user_agent,
            'Accept': 'application/json'
        })

    def _make_request(
        self,
        method: str,
        url: str,
        **kwargs: Any
    ) -> requests.Response:
        """Make HTTP request with retry logic."""
        kwargs.setdefault('timeout', self.timeout)

        @with_retry(
            max_retries=self.max_retries,
            retry_delays=self.retry_delays
        )
        def do_request() -> requests.Response:
            response = self._session.request(method, url, **kwargs)
            response.raise_for_status()
            return response

        if self.circuit_breaker:
            return self.circuit_breaker.call(do_request)
        return do_request()

    def get(self, url: str, **kwargs: Any) -> requests.Response:
        """GET request with retry logic."""
        return self._make_request('GET', url, **kwargs)

    def post(self, url: str, **kwargs: Any) -> requests.Response:
        """POST request with retry logic."""
        return self._make_request('POST', url, **kwargs)

    def get_json(self, url: str, **kwargs: Any) -> Any:
        """GET request returning JSON with error handling."""
        try:
            response = self.get(url, **kwargs)
            return response.json()
        except ValueError as e:
            raise APIError(
                code=ErrorCode.MALFORMED_JSON,
                original_exception=e,
                details={'url': url}
            )

    def close(self) -> None:
        """Close the session."""
        self._session.close()

    def __enter__(self) -> "RetryableSession":
        return self

    def __exit__(self, *args: Any) -> None:
        self.close()


@dataclass
class ErrorLog:
    """
    Error logging utility with history tracking.

    Maintains a log of errors with timestamps for debugging
    and monitoring.
    """
    max_entries: int = 1000
    _errors: List[Dict[str, Any]] = field(default_factory=list, init=False)
    _lock: threading.Lock = field(default_factory=threading.Lock, init=False)

    def log(self, error: CTGovError) -> None:
        """Add error to log."""
        with self._lock:
            entry = error.to_dict()
            self._errors.append(entry)

            # Trim if over limit
            if len(self._errors) > self.max_entries:
                self._errors = self._errors[-self.max_entries:]

    def get_recent(self, count: int = 10) -> List[Dict[str, Any]]:
        """Get most recent errors."""
        with self._lock:
            return self._errors[-count:]

    def get_by_code(self, code: ErrorCode) -> List[Dict[str, Any]]:
        """Get errors by error code."""
        with self._lock:
            return [e for e in self._errors if e['error_code'] == code.value]

    def clear(self) -> None:
        """Clear error log."""
        with self._lock:
            self._errors.clear()

    def summary(self) -> Dict[str, int]:
        """Get summary of error counts by type."""
        with self._lock:
            counts: Dict[str, int] = {}
            for entry in self._errors:
                name = entry.get('error_name', 'UNKNOWN')
                counts[name] = counts.get(name, 0) + 1
            return counts


# Global error log instance
error_log = ErrorLog()


def main() -> None:
    """Demo usage of the error handling module."""
    print("=" * 70)
    print("  Error Handling Module - Demo")
    print("=" * 70)

    # Demo 1: Basic error handling
    print("\n1. Basic Error Handling")
    print("-" * 40)

    try:
        raise ValidationError(
            code=ErrorCode.INVALID_NCT_ID,
            field="nct_id",
            details={'value': 'NCTABC123'}
        )
    except CTGovError as e:
        print(f"Caught error: {e}")
        print(f"Error dict: {e.to_dict()}")
        error_log.log(e)

    # Demo 2: Retry decorator
    print("\n2. Retry Decorator")
    print("-" * 40)

    call_count = 0

    @with_retry(max_retries=2, retry_delays=(0.1, 0.2))
    def flaky_function() -> str:
        nonlocal call_count
        call_count += 1
        if call_count < 3:
            raise requests.exceptions.ConnectionError("Simulated failure")
        return "Success!"

    try:
        result = flaky_function()
        print(f"Result after {call_count} attempts: {result}")
    except CTGovError as e:
        print(f"Failed: {e}")

    # Demo 3: Circuit breaker
    print("\n3. Circuit Breaker")
    print("-" * 40)

    breaker = CircuitBreaker(failure_threshold=3, reset_timeout=5)

    for i in range(5):
        try:
            def failing_call() -> None:
                raise Exception("Service unavailable")

            breaker.call(failing_call)
        except CircuitBreakerError as e:
            print(f"Attempt {i + 1}: Circuit breaker OPEN")
        except Exception as e:
            print(f"Attempt {i + 1}: Regular failure - {e}")

    print(f"Circuit state: {breaker.state.name}")

    # Demo 4: RetryableSession
    print("\n4. RetryableSession")
    print("-" * 40)

    session = RetryableSession(max_retries=1, timeout=5)
    try:
        # This will fail but demonstrates the pattern
        data = session.get_json("https://clinicaltrials.gov/api/v2/studies?query.cond=diabetes&pageSize=1")
        print(f"Fetched study count: {data.get('totalCount', 0)}")
    except CTGovError as e:
        print(f"Request error: {e.code.name}")
        error_log.log(e)

    # Demo 5: Error log summary
    print("\n5. Error Log Summary")
    print("-" * 40)
    print(f"Total errors logged: {len(error_log._errors)}")
    print(f"Summary by type: {error_log.summary()}")

    print("\n" + "=" * 70)
    print("  Demo complete!")
    print("=" * 70)


if __name__ == "__main__":
    main()
