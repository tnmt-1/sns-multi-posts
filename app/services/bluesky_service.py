import logging
from collections.abc import Mapping
from typing import Any

from atproto import Client, client_utils, models

from app.schemas.account import BlueskyAccount
from app.schemas.post import ImageData, PostResult
from app.services.base_service import BaseSNSProvider

logger = logging.getLogger(__name__)


class BlueskyService(BaseSNSProvider):
    PROVIDER_NAME = "bluesky"
    CHAR_LIMIT = 300

    def get_text_length(self, text: str) -> int:
        """
        Bluesky の文字数計算（単純な文字数）。
        """
        return len(text)

    def get_character_limit(self) -> int:
        return self.CHAR_LIMIT

    async def post(
        self,
        account: Mapping[str, Any],
        text: str,
        images: list[ImageData] | None = None,
        **kwargs: Any,
    ) -> PostResult:
        try:
            acc_model = BlueskyAccount.model_validate(account)
            resp = await self._post_internal(acc_model, text, images)

            # post_id を取得 (URI の最末尾)
            uri = getattr(resp, "uri", "")
            post_id = uri.split("/")[-1] if uri else None

            # Bluesky の URL 形式: https://bsky.app/profile/{handle}/post/{post_id}
            url = f"https://bsky.app/profile/{acc_model.handle}/post/{post_id}" if post_id else None

            return self._create_success_result(post_id=post_id, url=url)
        except Exception as e:
            logger.error(f"Bluesky post failed: {e}")
            return self._create_error_result(str(e))

    async def _post_internal(
        self,
        account: BlueskyAccount,
        text: str,
        images: list[ImageData] | None = None,
    ) -> Any:
        """Bluesky に投稿します（オプションで画像付き）。"""
        client = Client()
        client.login(account.handle, account.password)

        if not images:
            # テキストのみの投稿
            return client.send_post(text=text)

        # 画像付き投稿
        # Note: atproto SDK の upload_blob は同期実行
        blobs = []
        for img_bytes, _mime_type in images:
            blob_resp = client.upload_blob(img_bytes)
            blobs.append(models.AppBskyEmbedImages.Image(alt="", image=blob_resp.blob))

        embed = models.AppBskyEmbedImages.Main(images=blobs)

        # client_utils.TextBuilder を使うとメンションやリンクが自動で解決される
        tb = client_utils.TextBuilder()
        tb.text(text)

        return client.send_post(tb, embed=embed)
