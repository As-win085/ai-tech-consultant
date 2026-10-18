import httpx

from app.throttle import retry_delay_seconds, response_retry_after


def test_retry_after_header_takes_precedence_over_exponential_delay():
    assert retry_delay_seconds("12", attempt=2, base=1) == 12


def test_retry_after_gemini_retry_info_is_recognized():
    response = httpx.Response(
        429,
        json={"error": {"details": [{"@type": "type.googleapis.com/google.rpc.RetryInfo", "retryDelay": "17.5s"}]}},
    )
    assert response_retry_after(response) == "17.5"
