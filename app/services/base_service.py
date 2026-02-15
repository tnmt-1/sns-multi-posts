from typing import Any, Protocol, runtime_checkable

from app.schemas.post import ImageData, PostResult


@runtime_checkable
class BaseSNSProvider(Protocol):
    """SNSプロバイダーが実装すべき共通のインターフェース。

    `runtime_checkable` デコレータにより、実行時に `isinstance` を用いた
    型チェックが可能になっています。各 SNS プロバイダーはこのプロトコルを
    実装することで、`PostService` から統一的に扱われます。
    """

    async def post(
        self, text: str, images: list[ImageData] | None = None, account_data: dict[str, Any] | None = None
    ) -> PostResult:
        """SNS への一括投稿処理を定義します。

        Args:
            text (str): 投稿するテキスト。
            images (list[ImageData] | None): 投稿する画像のバイナリデータとメタデータのリスト。
            account_data (dict[str, Any] | None): セッションから取得した、
                プロバイダー固有のアカウント認証情報 (トークン、パスワード等)。

        Returns:
            PostResult: 投稿の成否と、失敗時のエラーメッセージを含むオブジェクト。
        """
        ...
