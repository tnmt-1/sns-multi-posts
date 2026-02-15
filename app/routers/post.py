"""SNS への投稿操作に関連するエンドポイントを定義するルーター。"""

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, Request, UploadFile
from fastapi.responses import RedirectResponse, Response
from fastapi.templating import Jinja2Templates

from app.services import PostService
from app.services.account_service import AccountManager, get_account_manager

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
    manager: AccountManager = Depends(get_account_manager),
) -> Response:
    """各SNSへメッセージを一括投稿します。

    Args:
        request (Request): FastAPIリクエスト。
        text (str): 投稿する本文。
        selected_accounts (list[str]): 選択されたアカウントIDリスト ('id@provider' 形式)。
        misskey_visibility (str): Misskeyの公開範囲。
        images (list[UploadFile] | None): 添付画像。
        manager (AccountManager): アカウント管理マネージャー。

    Returns:
        Response: ホームへのリダイレクト、またはエラー時の画面表示。
    """
    # 画像の処理
    images_data = await PostService.process_images(images)

    # バリデーション
    error_msg = PostService.validate_limits(manager, text, selected_accounts, len(images_data))
    if error_msg:
        return templates.TemplateResponse(
            "index.html",
            {
                "request": request,
                "error": error_msg,
                "accounts": manager.accounts,
            },
        )

    # 投稿実行
    result = await PostService.post_to_all(
        manager,
        text,
        selected_accounts,
        images_data,
        visibility=misskey_visibility,
    )

    if result.total_count == 0:
        request.session["flash_message"] = "送信先のアカウントが選択されていません。"
        request.session["flash_type"] = "error"
        return RedirectResponse(url="/", status_code=303)

    # 結果の構築
    message = f"{result.success_count} 個のアカウントに投稿しました。"
    if result.has_errors:
        message += " 失敗: " + ", ".join(result.error_messages)

    request.session["flash_message"] = message
    request.session["flash_type"] = "success" if not result.has_errors else "warning"

    return RedirectResponse(url="/", status_code=303)
