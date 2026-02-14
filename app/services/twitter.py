import io
import logging
import os
from datetime import datetime
from typing import Any

import tweepy

logger = logging.getLogger(__name__)


def _log_rate_limit_info(response: Any, endpoint: str) -> None:
    """Twitter API のレスポンスヘッダーからレート制限情報をログに記録します。"""
    try:
        # レスポンスヘッダーからレート制限情報の取得を試みる
        if hasattr(response, "_headers"):
            headers = response._headers
        elif hasattr(response, "headers"):
            headers = response.headers
        else:
            logger.debug(f"No headers found in response for {endpoint}")
            return

        limit = headers.get("x-rate-limit-limit")
        remaining = headers.get("x-rate-limit-remaining")
        reset = headers.get("x-rate-limit-reset")

        if limit or remaining or reset:
            reset_time = ""
            if reset:
                try:
                    reset_dt = datetime.fromtimestamp(int(reset))
                    reset_time = f", resets at {reset_dt.strftime('%Y-%m-%d %H:%M:%S')}"
                except (ValueError, TypeError):
                    reset_time = f", reset timestamp: {reset}"

            logger.info(f"Twitter API rate limit [{endpoint}]: {remaining}/{limit} requests remaining{reset_time}")
    except Exception as e:
        logger.debug(f"Failed to log rate limit info for {endpoint}: {e}")


def _get_filename_from_mime_type(mime_type: str) -> str:
    """MIME タイプに基づいて適切なファイル名を取得します。"""
    if "png" in mime_type:
        return "image.png"
    elif "gif" in mime_type:
        return "image.gif"
    return "image.jpg"


async def post_to_twitter(
    token: dict[str, Any] | str, text: str, images: list[tuple[bytes, str]] | None = None
) -> dict[str, Any]:
    """
    OAuth 1.0a 認証を使用して、画像付きのツイートを投稿します（オプション）。

    Args:
        token: oauth_token と oauth_token_secret を含む OAuth 1.0a トークン辞書
        text: ツイート本文
        images: (画像バイト, MIMEタイプ) のタプルのリスト（オプション）

    Returns:
        Twitter API からのツイートデータ

    Raises:
        tweepy.TooManyRequests: レート制限を超えた場合 (429)
        tweepy.TweepyException: その他の Twitter API エラーの場合
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

    # v1.1 API を使用してメディアをアップロード
    auth = tweepy.OAuth1UserHandler(consumer_key, consumer_secret, access_token, access_token_secret)
    api = tweepy.API(auth)

    media_ids: list[str] = []
    if images:
        for i, (image_bytes, mime_type) in enumerate(images):
            try:
                file_obj = io.BytesIO(image_bytes)
                filename = _get_filename_from_mime_type(mime_type)
                media = api.media_upload(filename=filename, file=file_obj)
                media_ids.append(media.media_id_string)
                logger.info(f"Uploaded image {i + 1}/{len(images)} (media_id: {media.media_id_string})")
            except tweepy.TooManyRequests as e:
                logger.error(f"Rate limit exceeded while uploading image {i + 1}: {e}")
                # 例外からレート制限情報の抽出を試みる
                if hasattr(e, "response"):
                    _log_rate_limit_info(e.response, "media_upload")
                raise
            except Exception as e:
                logger.error(f"Failed to upload image {i + 1}: {e}")
                raise

    # v2 API を使用してツイートを投稿
    client = tweepy.Client(
        consumer_key=consumer_key,
        consumer_secret=consumer_secret,
        access_token=access_token,
        access_token_secret=access_token_secret,
    )

    try:
        resp = client.create_tweet(text=text, media_ids=media_ids if media_ids else None)
        logger.info(f"Successfully created tweet (id: {resp.data.get('id', 'unknown')})")

        # 利用可能な場合はレート制限情報をログに記録
        if hasattr(resp, "_response"):
            _log_rate_limit_info(resp._response, "create_tweet")

        return resp.data
    except tweepy.TooManyRequests as e:
        logger.error(f"Rate limit exceeded while creating tweet: {e}")
        # 例外からレート制限情報の抽出を試みる
        if hasattr(e, "response"):
            _log_rate_limit_info(e.response, "create_tweet")
        raise
    except Exception as e:
        logger.error(f"Failed to create tweet: {e}")
        raise
