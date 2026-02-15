from collections.abc import Mapping
from typing import Any, Protocol, runtime_checkable

from app.schemas.post import ImageData, PostResult


@runtime_checkable
class BaseSNSProvider(Protocol):
    """SNSプロバイダーが実装すべき共通のインターフェース。

    `runtime_checkable` デコレータにより、実行時に `isinstance` を用いた
    型チェックが可能になっています。各 SNS プロバイダーはこのプロトコルを
    実装することで、`PostService` から統一的に扱われます。
    """

    PROVIDER_NAME: str

    def get_character_limit(self) -> int:
        """SNS の文字数制限を返します。"""
        ...

    def get_text_length(self, text: str) -> int:
        """SNS の仕様に基づいた文字数を計算します。"""
        ...

    async def post(
        self,
        account: Mapping[str, Any],
        text: str,
        images: list[ImageData] | None = None,
        **kwargs: Any,
    ) -> PostResult:
        """SNS への一括投稿処理を定義します。

        Args:
            account (Mapping[str, Any]): セッションから取得した、
                プロバイダー固有のアカウント認証情報。
            text (str): 投稿するテキスト。
            images (list[ImageData] | None): 投稿する画像のバイナリデータとメタデータのリスト。
            **kwargs (Any): プロバイダー固有の追加オプション。

        Returns:
            PostResult: 投稿の成否と、失敗時のエラーメッセージを含むオブジェクト。
        """
        ...

    def _create_success_result(self, post_id: str | None, url: str | None) -> PostResult:
        """成功時の PostResult を作成します。"""
        return PostResult(
            success=True,
            provider=self.PROVIDER_NAME,
            post_id=post_id,
            url=url,
        )

    def _create_error_result(self, error: str) -> PostResult:
        """失敗時の PostResult を作成します。"""
        return PostResult(
            success=False,
            provider=self.PROVIDER_NAME,
            error=error,
        )
