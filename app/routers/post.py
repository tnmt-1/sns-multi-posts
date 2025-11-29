import asyncio
import logging
from typing import Annotated, Any

from fastapi import APIRouter, File, Form, Request, UploadFile
from fastapi.responses import Response
from fastapi.templating import Jinja2Templates

from app.services import bluesky, misskey, twitter

router = APIRouter(prefix="/post", tags=["post"])
templates = Jinja2Templates(directory="app/templates")

# Configure logger
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
    # selected_accounts comes as a list of strings "provider:id"
    # But checking checkboxes with same name in HTML form results in a list

    accounts_session = request.session.get("accounts", {})

    # Process images
    images_data = []
    image_bytes = []
    if images:
        for img in images:
            if img.filename:
                content = await img.read()
                images_data.append((content, img.content_type or "image/jpeg"))
                image_bytes.append(content)

    if len(images_data) > 4:
        return templates.TemplateResponse(
            "index.html", {"request": request, "error": "Max 4 images allowed", "accounts": accounts_session}
        )

    # Validate character limit
    # Limits: Twitter 280, Bluesky 300, Misskey 3000
    # We use the minimum of selected platforms

    limits = {"twitter": 280, "bluesky": 300, "misskey": 3000}

    min_limit = 3000
    targets = []

    for acc_str in selected_accounts:
        provider, acc_id = acc_str.split(":", 1)
        if provider in limits:
            min_limit = min(min_limit, limits[provider])

        # Find account data
        if provider in accounts_session:
            for acc in accounts_session[provider]:
                if str(acc["id"]) == acc_id:
                    targets.append((provider, acc))
                    break

    if len(text) > min_limit:
        return templates.TemplateResponse(
            "index.html",
            {
                "request": request,
                "error": f"Text too long. Limit is {min_limit} characters.",
                "accounts": accounts_session,
            },
        )

    # Dispatch posts
    tasks = []

    for provider, acc in targets:
        if provider == "twitter":
            tasks.append(twitter.post_to_twitter(acc.get("token"), text, images_data))
        elif provider == "bluesky":
            tasks.append(bluesky.post_to_bluesky(acc, text, image_bytes))
        elif provider == "misskey":
            tasks.append(misskey.post_to_misskey(acc, text, image_bytes, visibility=misskey_visibility))

    # Run concurrently
    # We need to handle exceptions individually so one failure doesn't stop others

    async def safe_post(coro: Any, provider: str) -> dict[str, str]:
        try:
            await coro
            logger.info(f"Successfully posted to {provider}")
            return {"provider": provider, "status": "success"}
        except Exception as e:
            error_msg = f"Failed to post to {provider}: {type(e).__name__}: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return {"provider": provider, "status": "error", "message": str(e)}

    # Re-map tasks to include provider name for result tracking
    safe_tasks = []
    for i, (provider, _) in enumerate(targets):
        safe_tasks.append(safe_post(tasks[i], provider))

    post_results = await asyncio.gather(*safe_tasks)

    # Check for errors
    errors = [r for r in post_results if r["status"] == "error"]
    successes = [r for r in post_results if r["status"] == "success"]

    message = f"Posted to {len(successes)} accounts."
    if errors:
        message += f" Failed: {', '.join([e['provider'] for e in errors])}"

    # Store message in session for flash message
    request.session["flash_message"] = message
    request.session["flash_type"] = "success" if not errors else "warning"

    # Redirect to home page
    from starlette.responses import RedirectResponse

    return RedirectResponse(url="/", status_code=303)
