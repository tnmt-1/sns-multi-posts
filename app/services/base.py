from typing import Any, Protocol, runtime_checkable

from pydantic import BaseModel


class PostResult(BaseModel):
    success: bool
    provider: str
    post_id: str | None = None
    url: str | None = None
    error: str | None = None


@runtime_checkable
class SNSProvider(Protocol):
    def get_text_length(self, text: str) -> int:
        """SNS固有の文字数計算方法で長さを返します。"""
        ...

    def get_character_limit(self) -> int:
        """SNSの文字数制限を返します。"""
        ...

    async def post(
        self, account: dict[str, Any], text: str, images: list[tuple[bytes, str]] | None = None, **kwargs: Any
    ) -> PostResult:
        """SNSに投稿します。"""
        ...
