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
    """SNS への投稿処理を一括管理するサービス。

    複数プラットフォーム、複数アカウントへの同時投稿のオーケストレーション、
    画像の前処理（圧縮）、およびバリデーションを担当します。
    """

    @staticmethod
    async def process_images(images: list[UploadFile] | None) -> list[ImageData]:
        """アップロードされたファイルを `ImageData` 形式に変換し、最適化を行います。

        各 SNS プロバイダーの制限（主に 1MB 制限）に合わせて画像を自動的に圧縮します。

        Args:
            images (list[UploadFile] | None): FastAPI から受け取ったアップロードファイルのリスト。

        Returns:
            list[ImageData]: バイナリデータと MIME タイプを含むタプルのリスト。
        """
        images_data: list[ImageData] = []
        if images:
            for img in images:
                if img.filename:
                    content = await img.read()
                    # SNS プロバイダーの共通的な制限に合わせて圧縮
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
        """SNS プロバイダーごとの投稿制限を事前に検証します。

        文字数制限や画像枚数の上限をチェックし、問題があればエラーメッセージを返します。

        Args:
            manager (AccountManager): アカウント情報を解決するためのマネージャー。
            text (str): 投稿予定のテキスト。
            selected_account_ids (list[str]): ユーザーが選択した投稿先 ID リスト。
            image_count (int, optional): 添付画像の数。

        Returns:
            str | None: バリデーションエラーがある場合はその内容、問題なければ None。
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
        """指定されたすべてのアカウントに対して、並列で投稿を実行します。

        Args:
            manager (AccountManager): アカウント認証情報を取得するためのマネージャー。
            text (str): 投稿するテキスト。
            selected_account_ids (list[str]): 投稿先アカウント識別子のリスト。
            images_data (list[ImageData]): 前処理済みの画像データのリスト。
            **kwargs (Any): プロバイダー固有の追加オプション (例: `visibility`)。

        Returns:
            BulkPostResult: 各アカウントへの投稿結果をまとめたオブジェクト。
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
