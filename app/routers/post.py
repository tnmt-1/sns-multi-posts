import asyncio
import logging
from collections.abc import Mapping
from typing import Annotated, Any

from fastapi import APIRouter, File, Form, Request, UploadFile
from fastapi.responses import RedirectResponse, Response
from fastapi.templating import Jinja2Templates

from app.services import get_service
from app.services.base import ImageData, SNSProvider

router = APIRouter(prefix="/post", tags=["post"])
templates = Jinja2Templates(directory="app/templates")

# ロガーの設定
logger = logging.getLogger(__name__)


@router.post("/")
async def create_post(
    request: Request,
    text: Annotated[str, Form(...)],
    selected_accounts: Annotated[list[str], Form(...)],
    misskey_visibility: Annotated[str, Form()] = "public",
    images: Annotated[list[UploadFile] | None, File()] = None,
) -> Response:
    # selected_accounts は "provider:id" 形式の文字列リストとして渡されます
    accounts_session: dict[str, Any] = request.session.get("accounts", {})

    # 画像の処理
    images_data: list[ImageData] = []  # (コンテンツ, コンテンツタイプ) のリスト
    if images:
        for img in images:
            if img.filename:
                content = await img.read()
                images_data.append((content, img.content_type or "image/jpeg"))

    if len(images_data) > 4:
        return templates.TemplateResponse(
            "index.html", {"request": request, "error": "最大4枚まで画像を添付できます", "accounts": accounts_session}
        )

    targets: list[tuple[str, Mapping[str, Any], SNSProvider]] = []
    for acc_str in selected_accounts:
        provider, acc_id = acc_str.split(":", 1)
        service = get_service(provider)

        if not service:
            continue

        # 文字数制限の検証
        current_count = service.get_text_length(text)
        limit = service.get_character_limit()

        if current_count > limit:
            error_msg = f"{provider.capitalize()} の文字数制限を超えています。制限は {limit} 文字です（現在: {current_count} 文字）。"
            return templates.TemplateResponse(
                "index.html",
                {
                    "request": request,
                    "error": error_msg,
                    "accounts": accounts_session,
                },
            )

        # アカウントデータを探す
        if provider in accounts_session:
            for acc in accounts_session.get(provider, []):
                if str(acc.get("id")) == acc_id:
                    targets.append((provider, acc, service))
                    break

    # 投稿を配信
    tasks = []
    for provider, acc, service in targets:
        # プロバイダー固有の追加パラメータ
        kwargs: dict[str, Any] = {}
        if provider == "misskey":
            kwargs["visibility"] = misskey_visibility

        tasks.append(service.post(acc, text, images_data, **kwargs))

    # 並行して実行
    if not tasks:
        request.session["flash_message"] = "送信先のアカウントが選択されていません。"
        request.session["flash_type"] = "error"
        return RedirectResponse(url="/", status_code=303)

    results = await asyncio.gather(*tasks)

    # エラーの確認と集計
    errors = []
    success_count = 0
    for res in results:
        if res.success:
            logger.info(f"Successfully posted to {res.provider}")
            success_count += 1
        else:
            # エラーメッセージの翻訳
            error_msg = res.error or "Unknown error"
            if "429" in error_msg or "rate limit" in error_msg.lower():
                user_message = "API制限にかかりました。少し待ってから再度お試しください。"
            elif "401" in error_msg:
                user_message = "認証に失敗しました。アカウントを再連携してください。"
            elif "403" in error_msg:
                user_message = "アクセスが拒否されました。権限を確認してください。"
            else:
                user_message = error_msg

            logger.error(f"Failed to post to {res.provider}: {error_msg}")
            errors.append(f"{res.provider}: {user_message}")

    message = f"{success_count} 個のアカウントに投稿しました。"
    if errors:
        message += " 失敗: " + ", ".join(errors)

    # セッションにフラッシュメッセージを保存
    request.session["flash_message"] = message
    request.session["flash_type"] = "success" if not errors else "warning"

    return RedirectResponse(url="/", status_code=303)
