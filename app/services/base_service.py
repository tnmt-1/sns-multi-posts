from typing import Any, Protocol, runtime_checkable

from app.schemas.post import ImageData, PostResult


@runtime_checkable
class BaseSNSProvider(Protocol):
    """SNSプロバイダーの基本インターフェース。

    すべてのSNSプロバイダーはこのプロトコルに従い、共通の投稿メソッドを実装する必要があります。
    """

    async def post(
        self, text: str, images: list[ImageData] | None = None, account_data: dict[str, Any] | None = None
    ) -> PostResult:
        """SNSに投稿します。

        Args:
            text (str): 投稿する本文。
            images (list[ImageData] | None): 投稿する画像のリスト。
            account_data (dict[str, Any] | None): 投稿に使用するアカウントの認証情報。

        Returns:
            PostResult: 投稿結果。
         PostResult.success が True なら成功、False なら失敗。
        """
        ...
