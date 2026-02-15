import asyncio
import logging
from typing import Annotated, Any

from fastapi import APIRouter, File, Form, Request, UploadFile
from fastapi.responses import RedirectResponse, Response
from fastapi.templating import Jinja2Templates

from app.services import get_service
from app.services.base import AccountManager, ImageData

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
    """各SNSへメッセージを一括投稿します。

    Args:
        request (Request): FastAPIリクエスト。
        text (str): 投稿する本文。
        selected_accounts (list[str]): 選択されたアカウントIDリスト ('id@provider' 形式)。
        misskey_visibility (str): Misskeyの公開範囲。
        images (list[UploadFile] | None): 添付画像。

    Returns:
        Response: ホームへのリダイレクト、またはエラー時の画面表示。
    """
    manager = AccountManager(request.session)

    # 画像の処理
    images_data: list[ImageData] = []
    if images:
        for img in images:
            if img.filename:
                content = await img.read()
                images_data.append((content, img.content_type or "image/jpeg"))

    if len(images_data) > 4:
        return templates.TemplateResponse(
            "index.html",
            {
                "request": request,
                "error": "最大4枚まで画像を添付できます",
                "accounts": manager.accounts,
            },
        )

    # 投稿対象の解決と検証
    tasks = []
    targets_dict = manager.resolve_targets(selected_accounts)

    for provider, accounts in targets_dict.items():
        service = get_service(provider)
        if not service:
            continue

        for target_acc in accounts:
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
                        "accounts": manager.accounts,
                    },
                )

            kwargs: dict[str, Any] = {"visibility": misskey_visibility} if provider == "misskey" else {}
            tasks.append(service.post(target_acc, text, images_data, **kwargs))

    # 投稿を配信
    if not tasks:
        request.session["flash_message"] = "送信先のアカウントが選択されていません。"
        request.session["flash_type"] = "error"
        return RedirectResponse(url="/", status_code=303)

    results = await asyncio.gather(*tasks)

    # 結果の集計
    success_count = sum(1 for res in results if res.success)
    errors = [f"{res.provider}: {res.translated_error}" for res in results if not res.success]

    message = f"{success_count} 個のアカウントに投稿しました。"
    if errors:
        message += " 失敗: " + ", ".join(errors)

    request.session["flash_message"] = message
    request.session["flash_type"] = "success" if not errors else "warning"

    return RedirectResponse(url="/", status_code=303)
