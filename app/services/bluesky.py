import logging
from typing import Any

from atproto import Client, models

logger = logging.getLogger(__name__)


async def post_to_bluesky(account: dict[str, Any], text: str, images: list[bytes] | None = None) -> dict[str, Any]:
    """
    Post to Bluesky with optional images.

    Args:
        account: Account dict containing handle and password
        text: Post text content
        images: Optional list of image bytes

    Returns:
        Success status dict

    Raises:
        Exception: For any Bluesky API errors
    """
    if images is None:
        images = []

    try:
        client = Client()
        client.login(account["handle"], account["password"])
        logger.info(f"Logged in to Bluesky as {account['handle']}")

        # Upload images
        blob_refs = []
        if images:
            for i, image in enumerate(images):
                try:
                    upload = client.upload_blob(image)
                    blob_refs.append(models.AppBskyEmbedImages.Image(alt="Image", image=upload.blob))
                    logger.info(f"Uploaded image {i + 1}/{len(images)} to Bluesky")
                except Exception as e:
                    logger.error(f"Failed to upload image {i + 1} to Bluesky: {e}")
                    raise

        embed = None
        if blob_refs:
            embed = models.AppBskyEmbedImages.Main(images=blob_refs)

        client.send_post(text=text, embed=embed)
        logger.info("Successfully posted to Bluesky")

        # 他のサービス（Twitter, Misskey）と同様に辞書型で結果を返す
        return {"success": True}
    except Exception as e:
        logger.error(f"Failed to post to Bluesky: {type(e).__name__}: {e}", exc_info=True)
        raise
