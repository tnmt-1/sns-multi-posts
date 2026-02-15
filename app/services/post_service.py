import asyncio
import logging
from typing import Any

from fastapi import UploadFile

from app.schemas.post import BulkPostResult, ImageData
from app.utils.image_utils import compress_image

from .account_service import AccountManager
from .registry_service import get_service

logger = logging.getLogger(__name__)


class PostService:
    """投稿処理を統括するサービス。

    複数プラットフォームへの投稿フロー、バリデーション、並列実行を管理します。
    """

    @staticmethod
    async def process_images(images: list[UploadFile] | None) -> list[ImageData]:
        """UploadFileのリストをImageDataのリストに変換し、必要に応じて圧縮します。"""
        images_data: list[ImageData] = []
        if images:
            for img in images:
                if img.filename:
                    content = await img.read()
                    # 必要に応じて圧縮（1MB制限などを考慮）
                    compressed_content = compress_image(content)
                    images_data.append((compressed_content, img.content_type or "image/jpeg"))
        return images_data

    @staticmethod
    def validate_limits(
        manager: AccountManager,
        text: str,
        selected_account_ids: list[str],
        image_count: int = 0,
    ) -> str | None:
        """各サービスの制限を検証します（文字数、画像枚数）。

        Args:
            manager (AccountManager): アカウント管理マネージャー。
            text (str): 投稿する本文。
            selected_account_ids (list[str]): 選択されたアカウントIDリスト。
            image_count (int): 添付画像の枚数。

        Returns:
            str | None: 制限を超えている場合のエラーメッセージ。すべて正常なら None。
        """
        if image_count > 4:
            return "最大4枚まで画像を添付できます"

        targets_dict = manager.resolve_targets(selected_account_ids)

        for provider, accounts in targets_dict.items():
            service = get_service(provider)
            if not service or not accounts:
                continue

            current_count = service.get_text_length(text)
            limit = service.get_character_limit()
            if current_count > limit:
                return f"{provider.capitalize()} の文字数制限を超えています。制限は {limit} 文字です（現在: {current_count} 文字）。"

        return None

    @staticmethod
    async def post_to_all(
        manager: AccountManager,
        text: str,
        selected_account_ids: list[str],
        images_data: list[ImageData],
        **kwargs: Any,
    ) -> BulkPostResult:
        """選択されたすべてのアカウントにメッセージを投稿します。

        Args:
            manager (AccountManager): アカウント管理マネージャー。
            text (str): 投稿する本文。
            selected_account_ids (list[str]): 投稿対象のアカウントIDリスト。
            images_data (list[ImageData]): 投稿する画像のリスト。
            **kwargs (Any): 追加の投稿オプション（例: visibility）。

        Returns:
            BulkPostResult: 投稿結果。
        """
        targets_dict = manager.resolve_targets(selected_account_ids)
        tasks = []

        for provider, accounts in targets_dict.items():
            service = get_service(provider)
            if not service:
                continue

            for target_acc in accounts:
                # 特定のプロバイダー向けの追加引数（Misskeyの公開範囲など）を抽出
                provider_kwargs = kwargs.copy()
                if provider != "misskey":
                    provider_kwargs.pop("visibility", None)

                tasks.append(service.post(target_acc, text, images_data, **provider_kwargs))

        if not tasks:
            return BulkPostResult(results=[])

        results = await asyncio.gather(*tasks)
        return BulkPostResult(results=list(results))
