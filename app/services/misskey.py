import logging
from typing import Any, cast

import httpx

logger = logging.getLogger(__name__)


def _log_response_headers(headers: httpx.Headers, endpoint: str) -> None:
    """Log response headers including rate limit info if available."""
    # Misskey may include rate limit headers (depends on instance configuration)
    rate_limit_headers = {
        "x-ratelimit-limit": headers.get("x-ratelimit-limit"),
        "x-ratelimit-remaining": headers.get("x-ratelimit-remaining"),
        "x-ratelimit-reset": headers.get("x-ratelimit-reset"),
    }

    if any(rate_limit_headers.values()):
        logger.info(
            f"Misskey API [{endpoint}]: "
            f"Rate limit: {rate_limit_headers['x-ratelimit-remaining']}/{rate_limit_headers['x-ratelimit-limit']}, "
            f"reset: {rate_limit_headers['x-ratelimit-reset']}"
        )


async def post_to_misskey(
    account: dict[str, str],
    text: str,
    images: list[bytes] | None = None,
    visibility: str = "public",
) -> dict[str, Any]:
    """
    Post to Misskey with optional images.

    Args:
        account: Account dict containing instance and token
        text: Post text content
        images: Optional list of image bytes
        visibility: Post visibility (public, home, followers, specified)

    Returns:
        Misskey API response dict

    Raises:
        httpx.HTTPStatusError: For HTTP errors including 429 rate limit
    """
    if images is None:
        images = []
    instance = account["instance"]
    token = account["token"]

    file_ids: list[str] = []
    if images:
        async with httpx.AsyncClient() as client:
            for i, image in enumerate(images):
                try:
                    # Upload to drive/files/create
                    files = {"file": image}
                    data = {"i": token}
                    # httpx handles multipart if files is passed
                    # But we also need 'i' (token) in the body.
                    # Misskey API expects 'i' as a parameter.

                    resp = await client.post(f"https://{instance}/api/drive/files/create", data=data, files=files)
                    _log_response_headers(resp.headers, "drive/files/create")
                    resp.raise_for_status()
                    file_ids.append(resp.json()["id"])
                    logger.info(f"Uploaded image {i + 1}/{len(images)} to Misskey (file_id: {file_ids[-1]})")
                except httpx.HTTPStatusError as e:
                    if e.response.status_code == 429:
                        logger.error(f"Rate limit exceeded while uploading image {i + 1} to Misskey")
                        _log_response_headers(e.response.headers, "drive/files/create")
                    else:
                        logger.error(f"Failed to upload image {i + 1} to Misskey: {e.response.status_code}")
                    raise
                except Exception as e:
                    logger.error(f"Failed to upload image {i + 1} to Misskey: {e}")
                    raise

    url = f"https://{instance}/api/notes/create"
    payload: dict[str, Any] = {
        "i": token,
        "text": text,
        "visibility": visibility,
    }
    if file_ids:
        payload["fileIds"] = file_ids

    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(url, json=payload)
            _log_response_headers(resp.headers, "notes/create")
            resp.raise_for_status()
            logger.info(
                f"Successfully posted to Misskey (note_id: {resp.json().get('createdNote', {}).get('id', 'unknown')})"
            )
            # Misskey API のレスポンスはさまざまなフィールドを含むため、dict[str, Any] として扱う
            return cast(dict[str, Any], resp.json())
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 429:
            logger.error("Rate limit exceeded while creating Misskey note")
            _log_response_headers(e.response.headers, "notes/create")
        else:
            logger.error(f"Failed to create Misskey note: {e.response.status_code}")
        raise
    except Exception as e:
        logger.error(f"Failed to create Misskey note: {type(e).__name__}: {e}", exc_info=True)
        raise
