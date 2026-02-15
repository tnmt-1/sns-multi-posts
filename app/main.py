import logging
import os

from fastapi import Depends, FastAPI, Request
from fastapi.responses import Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware

from app.config import settings
from app.routers import auth, post
from app.services.base import AccountManager, get_account_manager

# ロガーの設定
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 起動時の検証
if not settings.twitter_client_id or not settings.twitter_client_secret:
    if settings.vercel:
        raise RuntimeError("Twitter API credentials are required in production (VERCEL=1)")
    else:
        logger.warning("Twitter API credentials are not set. Twitter login will not work.")

app = FastAPI(title="SNS Multi-Post", debug=settings.debug)

app.add_middleware(SessionMiddleware, secret_key=settings.secret_key)

# ディレクトリが存在する場合のみ静的ファイルをマウント
if os.path.exists("static"):
    app.mount("/static", StaticFiles(directory="static"), name="static")

# テンプレート設定
templates = Jinja2Templates(directory="app/templates")

app.include_router(auth.router)
app.include_router(post.router)


@app.get("/")
async def read_root(
    request: Request,
    manager: AccountManager = Depends(get_account_manager),
) -> Response:
    manager.save()  # 移行されたデータを永続化

    # セッションからフラッシュメッセージを取得
    flash_message = request.session.pop("flash_message", None)
    flash_type = request.session.pop("flash_type", None)

    context = {"request": request, "accounts": manager.accounts}

    if flash_message:
        if flash_type == "success":
            context["message"] = flash_message
        else:
            context["error"] = flash_message

    return templates.TemplateResponse("index.html", context)


@app.get("/health")
async def health_check() -> dict[str, str]:
    return {"status": "ok"}
