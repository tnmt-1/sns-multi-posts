import asyncio
import logging
import re
from typing import Annotated, Any

from fastapi import APIRouter, File, Form, Request, UploadFile
from fastapi.responses import Response
from fastapi.templating import Jinja2Templates

from app.services import bluesky, misskey, twitter

router = APIRouter(prefix="/post", tags=["post"])
templates = Jinja2Templates(directory="app/templates")

# ロガーの設定
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


@router.post("/")
async def create_post(
    request: Request,
    text: Annotated[str, Form(...)],
    selected_accounts: Annotated[list[str], Form(...)],
    misskey_visibility: Annotated[str, Form()] = "public",
    images: Annotated[list[UploadFile] | None, File()] = None,
) -> Response:
    # selected_accounts は "provider:id" 形式の文字列リストとして渡されます
    # HTMLフォームで同じ名前のチェックボックスを選択するとリストになります

    accounts_session = request.session.get("accounts", {})

    # 画像の処理
    images_data = []  # (コンテンツ, コンテンツタイプ) のリスト
    if images:
        for img in images:
            if img.filename:
                content = await img.read()
                images_data.append((content, img.content_type or "image/jpeg"))

    if len(images_data) > 4:
        return templates.TemplateResponse(
            "index.html", {"request": request, "error": "最大4枚まで画像を添付できます", "accounts": accounts_session}
        )

    # 文字数制限の検証
    # 文字数制限: Twitter 280, Bluesky 300, Misskey 3000
    limits = {"twitter": 280, "bluesky": 300, "misskey": 3000}

    def get_twitter_length(t: str) -> int:
        url_pattern = re.compile(r"https?://[^\s]+")
        urls = url_pattern.findall(t)
        base_len = len(url_pattern.sub("", t))
        return base_len + (len(urls) * 23)

    targets = []
    for acc_str in selected_accounts:
        provider, acc_id = acc_str.split(":", 1)

        # プロバイダーごとの文字数を計算
        if provider == "twitter":
            current_count = get_twitter_length(text)
        else:
            current_count = len(text)

        limit = limits.get(provider, 3000)
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
            for acc in accounts_session[provider]:
                if str(acc["id"]) == acc_id:
                    targets.append((provider, acc))
                    break

    # 投稿を配信
    tasks = []

    for provider, acc in targets:
        if provider == "twitter":
            tasks.append(twitter.post_to_twitter(acc.get("token"), text, images_data))
        elif provider == "bluesky":
            tasks.append(bluesky.post_to_bluesky(acc, text, images_data))
        elif provider == "misskey":
            tasks.append(misskey.post_to_misskey(acc, text, images_data, visibility=misskey_visibility))

    # 並行して実行
    # 1つの失敗が他に影響しないよう、例外を個別に処理します

    async def safe_post(coro: Any, provider: str) -> dict[str, str]:
        try:
            await coro
            logger.info(f"Successfully posted to {provider}")
            return {"provider": provider, "status": "success"}
        except Exception as e:
            error_type = type(e).__name__
            error_msg = str(e)

            # よりユーザーフレンドリーなエラーメッセージを提供
            if "429" in error_msg or "TooManyRequests" in error_type or "rate limit" in error_msg.lower():
                user_message = "API制限（レートリミット）にかかりました。少し待ってから再度お試しください。"
            elif "401" in error_msg or "Unauthorized" in error_type:
                user_message = "認証に失敗しました。アカウントを再連携してください。"
            elif "403" in error_msg or "Forbidden" in error_type:
                user_message = "アクセスが拒否されました。パーミッションを確認してください。"
            else:
                user_message = f"{error_type}: {error_msg}"

            full_error_msg = f"Failed to post to {provider}: {error_type}: {error_msg}"
            logger.error(full_error_msg, exc_info=True)
            return {"provider": provider, "status": "error", "message": user_message}

    # 結果追跡のためにプロバイダー名を含むようにタスクを再マッピング
    safe_tasks = []
    for i, (provider, _) in enumerate(targets):
        safe_tasks.append(safe_post(tasks[i], provider))

    post_results = await asyncio.gather(*safe_tasks)

    # エラーの確認
    errors = [r for r in post_results if r["status"] == "error"]
    successes = [r for r in post_results if r["status"] == "success"]

    message = f"{len(successes)} 個のアカウントに投稿しました。"
    if errors:
        message += f" 失敗: {', '.join([e['provider'] for e in errors])}"

    # セッションにフラッシュメッセージを保存
    request.session["flash_message"] = message
    request.session["flash_type"] = "success" if not errors else "warning"

    # ホームページへリダイレクト
    from starlette.responses import RedirectResponse

    return RedirectResponse(url="/", status_code=303)
