import logging
import re
from collections.abc import Mapping
from typing import Any

from atproto import Client, client_utils, models

from app.schemas.account import BlueskyAccount
from app.schemas.post import ImageData, PostResult
from app.services.base_service import BaseSNSProvider

logger = logging.getLogger(__name__)


class BlueskyPostContent:
    """Bluesky の投稿内容（テキスト、リンク、メンション等）をカプセル化するドメインモデル。

    このクラスは Bluesky のリッチテキスト構築ルールをカプセル化し、
    I/O（API通信）から独立した純粋なロジックを提供します。
    """

    def __init__(self, text: str):
        self.text = text

    def to_text_builder(self) -> client_utils.TextBuilder:
        """テキスト内のURLを抽出し、リンクファセットを含むTextBuilderを構築します。

        Returns:
            client_utils.TextBuilder: 構築済みのTextBuilder。
        """
        tb = client_utils.TextBuilder()
        last_index = 0
        # シンプルな URL 正規表現でテキストを分割・処理
        for match in re.finditer(r"https?://[^\s]+", self.text):
            # URL の前のテキストを追加
            tb.text(self.text[last_index : match.start()])
            # URL 部分をリンクとして追加
            url = match.group(0)
            tb.link(url, url)
            last_index = match.end()
        # 残りのテキストを追加
        tb.text(self.text[last_index:])
        return tb


class BlueskyService(BaseSNSProvider):
    """Bluesky への投稿を管理するサービス。

    atproto SDK を使用し、ID/パスワードによるセッション認証と
    テキスト・画像投稿をサポートします。
    """

    PROVIDER_NAME = "bluesky"
    CHAR_LIMIT = 300

    def get_text_length(self, text: str) -> int:
        """Bluesky の仕様に基づいた文字数を計算します。

        現在の実装では単純な文字数を返します。

        Args:
            text (str): 計算対象のテキスト。

        Returns:
            int: 文字数。
        """
        return len(text)

    def get_character_limit(self) -> int:
        """Bluesky の文字数制限を取得します。

        Returns:
            int: 最大文字数（300文字）。
        """
        return self.CHAR_LIMIT

    async def post(
        self,
        account: Mapping[str, Any],
        text: str,
        images: list[ImageData] | None = None,
        **kwargs: Any,
    ) -> PostResult:
        """Bluesky に投稿します。

        Args:
            account (Mapping[str, Any]): 認証情報（BlueskyAccount）を含むアカウントデータ。
            text (str): 投稿本文。
            images (list[ImageData] | None): 添付する画像のリスト。
            **kwargs (Any): 追加の引数（現状は未使用）。

        Returns:
            PostResult: 投稿結果。
        """
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
        """atproto API を呼び出して実際に投稿処理を行います。

        Args:
            account (BlueskyAccount): 認証済みのハンドルとパスワード。
            text (str): 投稿本文。
            images (list[ImageData] | None): アップロードする画像のリスト。

        Returns:
            Any: Bluesky API からのレスポンスオブジェクト。
        """
        client = Client()
        client.login(account.handle, account.password)

        # ドメインモデルを使用してリッチテキストを構築
        content = BlueskyPostContent(text)
        tb = content.to_text_builder()

        if not images:
            # テキストのみの投稿（リンク対応済み tb を使用）
            return client.send_post(text=tb, langs=["ja"])

        # 画像付き投稿
        # Note: atproto SDK の upload_blob は同期実行
        blobs = []
        for img_bytes, _mime_type in images:
            blob_resp = client.upload_blob(img_bytes)
            blobs.append(models.AppBskyEmbedImages.Image(alt="", image=blob_resp.blob))

        embed = models.AppBskyEmbedImages.Main(images=blobs)

        return client.send_post(tb, embed=embed, langs=["ja"])
