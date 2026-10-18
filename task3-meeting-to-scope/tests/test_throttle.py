import httpx

from app.throttle import retry_delay_seconds, response_retry_after


def test_retry_after_header_takes_precedence_over_backoff():
    assert retry_delay_seconds("9", attempt=3, base=1) == 9


def test_retry_after_google_body_is_recognized():
    response = httpx.Response(
        429,
        json={"error": {"details": [{"@type": "type.googleapis.com/google.rpc.RetryInfo", "retryDelay": "17s"}]}},
    )
    assert response_retry_after(response) == "17"
