import io
import logging
import re
from collections.abc import Mapping
from datetime import datetime
from typing import Any, cast

import httpx
import tweepy

from app.config import settings
from app.schemas.account import TwitterAccount, TwitterToken
from app.schemas.post import ImageData, PostResult
from app.services.base_service import BaseSNSProvider

logger = logging.getLogger(__name__)


class TwitterService(BaseSNSProvider):
    PROVIDER_NAME = "twitter"
    CHAR_LIMIT = 280  # 投稿内容によっては140の場合もあるが、一般的には280 (日本語は140)

    def get_text_length(self, text: str) -> int:
        """
        Twitter の文字数計算（URL は 23 文字としてカウント）。
        """
        url_pattern = re.compile(r"https?://[^\s]+")
        urls = url_pattern.findall(text)
        base_len = len(url_pattern.sub("", text))
        return base_len + (len(urls) * 23)

    def get_character_limit(self) -> int:
        return 140  # 日本語向けの制限

    async def post(
        self,
        account: Mapping[str, Any],
        text: str,
        images: list[ImageData] | None = None,
        **kwargs: Any,
    ) -> PostResult:
        try:
            acc_model = TwitterAccount.model_validate(account)
            resp_data = await self._post_internal(acc_model.token, text, images)
            post_id = str(resp_data.get("id"))
            # Twitter の URL 形式: https://twitter.com/user/status/id
            return self._create_success_result(
                post_id=post_id,
                url=f"https://twitter.com/i/web/status/{post_id}",
            )
        except Exception as e:
            logger.error(f"Twitter post failed: {e}")
            return self._create_error_result(str(e))

    async def _post_internal(
        self, token: TwitterToken, text: str, images: list[ImageData] | None = None
    ) -> dict[str, str | int]:
        """OAuth 1.0a 認証を使用して、画像付きのツイートを投稿します（オプション）。"""
        if images is None:
            images = []

        consumer_key = settings.twitter_client_id
        consumer_secret = settings.twitter_client_secret
        access_token = token.oauth_token
        access_token_secret = token.oauth_token_secret

        if not consumer_key or not consumer_secret or not access_token or not access_token_secret:
            raise ValueError("Missing OAuth 1.0a credentials")

        # v1.1 API を使用してメディアをアップロード
        auth = tweepy.OAuth1UserHandler(consumer_key, consumer_secret, access_token, access_token_secret)
        api = tweepy.API(auth)

        media_ids: list[str] = []
        for i, (image_bytes, mime_type) in enumerate(images):
            try:
                file_obj = io.BytesIO(image_bytes)
                filename = self._get_filename_from_mime_type(mime_type)
                media = api.media_upload(filename=filename, file=file_obj)
                media_ids.append(media.media_id_string)
                logger.info(f"Uploaded image {i + 1}/{len(images)} (media_id: {media.media_id_string})")
            except tweepy.TooManyRequests as e:
                if hasattr(e, "response"):
                    self._log_rate_limit_info(e.response, "media_upload")
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
                self._log_rate_limit_info(resp._response, "create_tweet")

            return resp.data
        except tweepy.TooManyRequests as e:
            if hasattr(e, "response"):
                self._log_rate_limit_info(e.response, "create_tweet")
            raise
        except Exception as e:
            logger.error(f"Failed to create tweet: {e}")
            raise

    def _log_rate_limit_info(self, response: httpx.Response | object, endpoint: str) -> None:
        """Twitter API のレスポンスヘッダーからレート制限情報をログに記録します。"""
        try:
            headers: Mapping[str, Any] = {}
            if isinstance(response, httpx.Response):
                headers = response.headers
            elif hasattr(response, "_headers"):
                headers = cast(Mapping[str, Any], response._headers)
            elif hasattr(response, "headers"):
                headers = cast(Mapping[str, Any], response.headers)
            else:
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

    def _get_filename_from_mime_type(self, mime_type: str) -> str:
        """MIME タイプに基づいて適切なファイル名を取得します。"""
        if "png" in mime_type:
            return "image.png"
        elif "gif" in mime_type:
            return "image.gif"
        return "image.jpg"
