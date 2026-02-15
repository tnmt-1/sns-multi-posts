import asyncio
import logging
from typing import Any

from pydantic import BaseModel

from .base import AccountManager, ImageData, PostResult
from .registry import get_service

logger = logging.getLogger(__name__)


class BulkPostResult(BaseModel):
    """複数アカウントへの投稿結果をまとめるモデル。

    Attributes:
        results (list[PostResult]): 各アカウントへの投稿結果のリスト。
    """

    results: list[PostResult]

    @property
    def success_count(self) -> int:
        """成功した投稿の総数を返します。"""
        return sum(1 for res in self.results if res.success)

    @property
    def total_count(self) -> int:
        """試行した投稿の総数を返します。"""
        return len(self.results)

    @property
    def error_messages(self) -> list[str]:
        """失敗した投稿のエラーメッセージ一覧を返します。

        Returns:
            list[str]: "プロバイダー: エラー内容" 形式のリスト。
        """
        return [f"{res.provider}: {res.translated_error}" for res in self.results if not res.success]

    @property
    def has_errors(self) -> bool:
        """一つ以上の投稿が失敗したかどうかを返します。"""
        return any(not res.success for res in self.results)


class PostService:
    """投稿処理を統括するサービス。

    複数プラットフォームへの投稿フロー、バリデーション、並列実行を管理します。
    """

    @staticmethod
    def validate_limits(
        manager: AccountManager,
        text: str,
        selected_account_ids: list[str],
    ) -> str | None:
        """各サービスの文字数制限を検証します。

        Args:
            manager (AccountManager): アカウント管理マネージャー。
            text (str): 投稿する本文。
            selected_account_ids (list[str]): 選択されたアカウントIDリスト。

        Returns:
            str | None: 制限を超えている場合のエラーメッセージ。すべて正常なら None。
        """
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
