import logging
from typing import Any, cast

import httpx

from app.services.base import PostResult

logger = logging.getLogger(__name__)


class MisskeyService:
    PROVIDER_NAME = "misskey"
    CHAR_LIMIT = 3000

    def get_text_length(self, text: str) -> int:
        return len(text)

    def get_character_limit(self) -> int:
        return self.CHAR_LIMIT

    async def post(
        self,
        account: dict[str, Any],
        text: str,
        images: list[tuple[bytes, str]] | None = None,
        **kwargs: Any,
    ) -> PostResult:
        try:
            visibility = kwargs.get("visibility", "public")
            resp = await post_to_misskey(account, text, images, visibility=visibility)
            note = resp.get("createdNote", {})
            post_id = note.get("id")
            instance = account.get("instance")
            url = f"https://{instance}/notes/{post_id}" if instance and post_id else None

            return PostResult(
                success=True,
                provider=self.PROVIDER_NAME,
                post_id=post_id,
                url=url,
            )
        except Exception as e:
            logger.error(f"Misskey post failed: {e}")
            return PostResult(success=False, provider=self.PROVIDER_NAME, error=str(e))


def _log_response_headers(headers: httpx.Headers, endpoint: str) -> None:
    """可能であればレート制限情報を含むレスポンスヘッダーをログに記録します。"""
    # Misskey はレート制限ヘッダーを含む場合があります（インスタンスの設定によります）
    rate_limit_headers = {
        "x-ratelimit-limit": headers.get("x-ratelimit-limit"),
        "x-ratelimit-remaining": headers.get("x-ratelimit-remaining"),
        "x-ratelimit-reset": headers.get("x-ratelimit-reset"),
    }

    if any(rate_limit_headers.values()):
        logger.info(
            f"Misskey API [{endpoint}]: "
            f"Rate limit: {rate_limit_headers['x-ratelimit-remaining']}/{rate_limit_headers['x-ratelimit-limit']}, "
            f"reset: {rate_limit_headers['x-ratelimit-reset']}"
        )


async def post_to_misskey(
    account: dict[str, str],
    text: str,
    images: list[tuple[bytes, str]] | None = None,
    visibility: str = "public",
) -> dict[str, Any]:
    """
    Misskey に投稿します（オプションで画像付き）。

    Args:
        account: インスタンスとトークンを含むアカウント辞書
        text: 投稿テキスト
        images: (画像バイト, MIMEタイプ) のタプルのリスト（オプション）
        visibility: 投稿の公開範囲 (public, home, followers, specified)

    Returns:
        Misskey API のレスポンス辞書

    Raises:
        httpx.HTTPStatusError: 429 レート制限を含む HTTP エラーの場合
    """
    if images is None:
        images = []
    instance = account["instance"]
    token = account["token"]

    file_ids: list[str] = []
    if images:
        async with httpx.AsyncClient() as client:
            for i, (image_byte_data, _mime_type) in enumerate(images):
                try:
                    # drive/files/create にアップロード
                    files = {"file": image_byte_data}
                    data = {"i": token}
                    # files が渡されると httpx はマルチパートを処理します
                    # ただし、ボディに 'i' (トークン) も必要です。
                    # Misskey API はパラメータとして 'i' を期待しています。

                    resp = await client.post(f"https://{instance}/api/drive/files/create", data=data, files=files)
                    _log_response_headers(resp.headers, "drive/files/create")
                    resp.raise_for_status()
                    file_ids.append(resp.json()["id"])
                    logger.info(f"Uploaded image {i + 1}/{len(images)} to Misskey (file_id: {file_ids[-1]})")
                except httpx.HTTPStatusError as e:
                    if e.response.status_code == 429:
                        logger.error(f"Rate limit exceeded while uploading image {i + 1} to Misskey")
                        _log_response_headers(e.response.headers, "drive/files/create")
                    else:
                        logger.error(f"Failed to upload image {i + 1} to Misskey: {e.response.status_code}")
                    raise
                except Exception as e:
                    logger.error(f"Failed to upload image {i + 1} to Misskey: {e}")
                    raise

    url = f"https://{instance}/api/notes/create"
    payload: dict[str, Any] = {
        "i": token,
        "text": text,
        "visibility": visibility,
    }
    if file_ids:
        payload["fileIds"] = file_ids

    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(url, json=payload)
            _log_response_headers(resp.headers, "notes/create")
            resp.raise_for_status()
            logger.info(
                f"Successfully posted to Misskey (note_id: {resp.json().get('createdNote', {}).get('id', 'unknown')})"
            )
            # Misskey API のレスポンスはさまざまなフィールドを含むため、dict[str, Any] として扱う
            return cast(dict[str, Any], resp.json())
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 429:
            logger.error("Rate limit exceeded while creating Misskey note")
            _log_response_headers(e.response.headers, "notes/create")
        else:
            logger.error(f"Failed to create Misskey note: {e.response.status_code}")
        raise
    except Exception as e:
        logger.error(f"Failed to create Misskey note: {type(e).__name__}: {e}", exc_info=True)
        raise
