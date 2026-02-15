import logging
from collections.abc import Mapping
from typing import Any

import httpx

from app.schemas.account import MisskeyAccount
from app.schemas.post import ImageData, PostResult
from app.services.base_service import BaseSNSProvider

logger = logging.getLogger(__name__)


class MisskeyService(BaseSNSProvider):
    """Misskey への投稿を管理するサービス。

    Misskey API を直接呼び出し、画像アップロードとノートの作成をサポートします。
    """

    PROVIDER_NAME = "misskey"
    CHAR_LIMIT = 3000

    def get_text_length(self, text: str) -> int:
        """Misskey の仕様に基づいた文字数を計算します。

        Args:
            text (str): 計算対象のテキスト。

        Returns:
            int: 文字数。
        """
        return len(text)

    def get_character_limit(self) -> int:
        """Misskey の文字数制限を取得します。

        Returns:
            int: 最大文字数（3000文字）。
        """
        return self.CHAR_LIMIT

    async def post(
        self,
        account: Mapping[str, Any],
        text: str,
        images: list[ImageData] | None = None,
        **kwargs: Any,
    ) -> PostResult:
        """Misskey にノートを投稿します。

        Args:
            account (Mapping[str, Any]): 認証情報（MisskeyAccount）を含むアカウントデータ。
            text (str): ノート本文。
            images (list[ImageData] | None): 添付する画像のリスト。
            **kwargs (Any): 追加の引数（visibility: 公開範囲など）。

        Returns:
            PostResult: 投稿結果。
        """
        try:
            acc_model = MisskeyAccount.model_validate(account)
            visibility = str(kwargs.get("visibility", "public"))
            resp = await self._post_internal(acc_model, text, images, visibility=visibility)
            note = resp.get("createdNote", {})
            post_id = note.get("id")
            instance = acc_model.instance
            url = f"https://{instance}/notes/{post_id}" if instance and post_id else None

            return self._create_success_result(post_id=post_id, url=url)
        except Exception as e:
            logger.error(f"Misskey post failed: {e}")
            return self._create_error_result(str(e))

    async def _post_internal(
        self,
        account: MisskeyAccount,
        text: str,
        images: list[ImageData] | None = None,
        visibility: str = "public",
    ) -> dict[str, Any]:
        """Misskey API を呼び出して実際に投稿処理を行政します。

        1. 画像がある場合は /api/drive/files/create でアップロードします。
        2. /api/notes/create でノートを作成します。

        Args:
            account (MisskeyAccount): 認証済みのインスタンス名とトークン。
            text (str): ノート本文。
            images (list[ImageData] | None): アップロードする画像のリスト。
            visibility (str): 公開範囲。

        Returns:
            dict[str, Any]: Misskey API からのレスポンス。
        """
        if images is None:
            images = []
        instance = account.instance
        token = account.token

        file_ids: list[str] = []
        async with httpx.AsyncClient() as client:
            for i, (image_byte_data, _mime_type) in enumerate(images):
                try:
                    # drive/files/create にアップロード
                    files = {"file": image_byte_data}
                    data = {"i": token}
                    resp = await client.post(f"https://{instance}/api/drive/files/create", data=data, files=files)
                    self._log_response_headers(resp.headers, "drive/files/create")
                    resp.raise_for_status()
                    file_ids.append(resp.json()["id"])
                    logger.info(f"Uploaded image {i + 1}/{len(images)} to Misskey (file_id: {file_ids[-1]})")
                except httpx.HTTPStatusError as e:
                    if e.response.status_code == 429:
                        logger.error(f"Rate limit exceeded while uploading image {i + 1} to Misskey")
                        self._log_response_headers(e.response.headers, "drive/files/create")
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

        async with httpx.AsyncClient() as client:
            resp = await client.post(url, json=payload)
            self._log_response_headers(resp.headers, "notes/create")
            resp.raise_for_status()
            logger.info(
                f"Successfully posted to Misskey (note_id: {resp.json().get('createdNote', {}).get('id', 'unknown')})"
            )
            return resp.json()

    def _log_response_headers(self, headers: httpx.Headers, endpoint: str) -> None:
        """レスポンスヘッダーからレート制限情報を抽出し、ログに記録します。

        Args:
            headers (httpx.Headers): API レスポンスヘッダー。
            endpoint (str): 対象のエンドポイント名（ログ出力用）。
        """
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
