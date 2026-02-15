from pydantic import BaseModel


class PostResult(BaseModel):
    """SNSへの投稿結果を保持するモデル。

    Attributes:
        success (bool): 投稿が成功したかどうか。
        provider (str): 投稿先のプロバイダー名（twitter, bluesky, misskeyなど）。
        post_id (str | None): SNS側で発行された投稿ID。
        url (str | None): 投稿された内容のURL。
        error (str | None): 失敗時のエラーメッセージ。
    """

    success: bool
    provider: str
    post_id: str | None = None
    url: str | None = None
    error: str | None = None

    @property
    def translated_error(self) -> str:
        """エラー内容をユーザーフレンドリーな日本語に翻訳します。

        Returns:
            str: 翻訳されたエラーメッセージ。
        """
        if self.success:
            return ""

        msg = self.error or "Unknown error"
        msg_lower = msg.lower()

        if "429" in msg or "rate limit" in msg_lower:
            return "API制限にかかりました。少し待ってから再度お試しください。"
        if "401" in msg or "unauthorized" in msg_lower:
            return "認証に失敗しました。アカウントを再連携してください。"
        if "403" in msg or "forbidden" in msg_lower:
            return "アクセスが拒否されました。権限を確認してください。"

        return msg


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


class BlueskyMetadata(BaseModel):
    """Blueskyのリンクプレビュー用メタデータ。"""

    title: str
    description: str
    image: str


# 画像データの型定義 (バイトデータ, MIMEタイプ)
type ImageData = tuple[bytes, str]
