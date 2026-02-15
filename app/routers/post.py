import logging
from typing import Annotated

from fastapi import APIRouter, File, Form, Request, UploadFile
from fastapi.responses import RedirectResponse, Response
from fastapi.templating import Jinja2Templates

from app.services import PostService
from app.services.base import AccountManager, ImageData

router = APIRouter(prefix="/post", tags=["post"])
templates = Jinja2Templates(directory="app/templates")

# ロガーの設定
logger = logging.getLogger(__name__)


async def _process_images(images: list[UploadFile] | None) -> list[ImageData]:
    """UploadFileのリストをImageDataのリストに変換します。

    Args:
        images (list[UploadFile] | None): FastAPIから受け取ったファイルのリスト。

    Returns:
        list[ImageData]: サービス層で扱える画像データのリスト。
    """
    images_data: list[ImageData] = []
    if images:
        for img in images:
            if img.filename:
                content = await img.read()
                images_data.append((content, img.content_type or "image/jpeg"))
    return images_data


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
    images_data = await _process_images(images)

    if len(images_data) > 4:
        return templates.TemplateResponse(
            "index.html",
            {
                "request": request,
                "error": "最大4枚まで画像を添付できます",
                "accounts": manager.accounts,
            },
        )

    # バリデーション
    error_msg = PostService.validate_limits(manager, text, selected_accounts)
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
