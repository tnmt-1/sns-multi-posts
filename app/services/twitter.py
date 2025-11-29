import io
import logging
import os
from typing import Any

import tweepy

logger = logging.getLogger(__name__)


async def refresh_twitter_token(token: dict[str, Any]) -> dict[str, Any]:
    # OAuth 1.0a tokens do not expire in the same way as OAuth 2.0
    # and do not use refresh tokens.
    return token


async def post_to_twitter(
    token: dict[str, Any] | str, text: str, images: list[tuple[bytes, str]] | None = None
) -> dict[str, Any]:
    if images is None:
        images = []

    # Token is expected to be a dict with oauth_token and oauth_token_secret
    if not isinstance(token, dict):
        raise ValueError("Token must be a dictionary for OAuth 1.0a")

    consumer_key = os.getenv("TWITTER_CLIENT_ID")
    consumer_secret = os.getenv("TWITTER_CLIENT_SECRET")

    access_token = token.get("oauth_token")
    access_token_secret = token.get("oauth_token_secret")

    if not consumer_key or not consumer_secret or not access_token or not access_token_secret:
        raise ValueError("Missing OAuth 1.0a credentials")

    # 1. Upload Media (v1.1) using tweepy.API
    auth = tweepy.OAuth1UserHandler(consumer_key, consumer_secret, access_token, access_token_secret)
    api = tweepy.API(auth)

    media_ids: list[str] = []
    if images:
        for image_bytes, mime_type in images:
            # Create a file-like object from bytes
            file_obj = io.BytesIO(image_bytes)
            # We need a filename for Tweepy to guess the type, or just dummy
            filename = "image.jpg"
            if "png" in mime_type:
                filename = "image.png"
            elif "gif" in mime_type:
                filename = "image.gif"

            # Upload
            # media_upload returns a Media object
            media = api.media_upload(filename=filename, file=file_obj)
            media_ids.append(media.media_id_string)

    # 2. Post Tweet (v2) using tweepy.Client
    client = tweepy.Client(
        consumer_key=consumer_key,
        consumer_secret=consumer_secret,
        access_token=access_token,
        access_token_secret=access_token_secret,
    )

    resp = client.create_tweet(text=text, media_ids=media_ids if media_ids else None)

    # resp.data is a dict-like object
    return resp.data
