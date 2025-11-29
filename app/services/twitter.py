import io
import logging
import os
from typing import Any

import tweepy

logger = logging.getLogger(__name__)


def _get_filename_from_mime_type(mime_type: str) -> str:
    """Get appropriate filename based on MIME type."""
    if "png" in mime_type:
        return "image.png"
    elif "gif" in mime_type:
        return "image.gif"
    return "image.jpg"


async def post_to_twitter(
    token: dict[str, Any] | str, text: str, images: list[tuple[bytes, str]] | None = None
) -> dict[str, Any]:
    """
    Post a tweet with optional images using OAuth 1.0a authentication.

    Args:
        token: OAuth 1.0a token dict containing oauth_token and oauth_token_secret
        text: Tweet text content
        images: Optional list of (image_bytes, mime_type) tuples

    Returns:
        Tweet data from Twitter API
    """
    if images is None:
        images = []

    if not isinstance(token, dict):
        raise ValueError("Token must be a dictionary for OAuth 1.0a")

    consumer_key = os.getenv("TWITTER_CLIENT_ID")
    consumer_secret = os.getenv("TWITTER_CLIENT_SECRET")
    access_token = token.get("oauth_token")
    access_token_secret = token.get("oauth_token_secret")

    if not consumer_key or not consumer_secret or not access_token or not access_token_secret:
        raise ValueError("Missing OAuth 1.0a credentials")

    # Upload media using v1.1 API
    auth = tweepy.OAuth1UserHandler(consumer_key, consumer_secret, access_token, access_token_secret)
    api = tweepy.API(auth)

    media_ids: list[str] = []
    if images:
        for image_bytes, mime_type in images:
            file_obj = io.BytesIO(image_bytes)
            filename = _get_filename_from_mime_type(mime_type)
            media = api.media_upload(filename=filename, file=file_obj)
            media_ids.append(media.media_id_string)

    # Post tweet using v2 API
    client = tweepy.Client(
        consumer_key=consumer_key,
        consumer_secret=consumer_secret,
        access_token=access_token,
        access_token_secret=access_token_secret,
    )

    resp = client.create_tweet(text=text, media_ids=media_ids if media_ids else None)
    return resp.data
