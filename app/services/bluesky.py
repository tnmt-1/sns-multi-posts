import io
import logging
from typing import Any

from atproto import Client, models
from PIL import Image

logger = logging.getLogger(__name__)


def _compress_image(image_bytes: bytes, max_size: int = 975000) -> bytes:
    """
    Compress image to be under max_size bytes.
    Bluesky has a strict blob limit of around 1MB (approx 976KB).
    """
    if len(image_bytes) <= max_size:
        return image_bytes

    try:
        img = Image.open(io.BytesIO(image_bytes))

        # Convert to RGB if necessary (e.g. for PNGs with transparency to JPEG)
        if img.mode in ("RGBA", "P"):
            img = img.convert("RGB")

        # Initial attempt: convert to JPEG with high quality
        output = io.BytesIO()
        img.save(output, format="JPEG", quality=85)
        compressed_data = output.getvalue()

        if len(compressed_data) <= max_size:
            return compressed_data

        # If still too big, try reducing quality
        for quality in [70, 50, 30]:
            output = io.BytesIO()
            img.save(output, format="JPEG", quality=quality)
            compressed_data = output.getvalue()
            if len(compressed_data) <= max_size:
                return compressed_data

        # If still too big, resize
        while len(compressed_data) > max_size:
            width, height = img.size
            ratio = 0.8
            new_width = int(width * ratio)
            new_height = int(height * ratio)
            img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)

            output = io.BytesIO()
            img.save(output, format="JPEG", quality=30)
            compressed_data = output.getvalue()

            if new_width < 100 or new_height < 100:
                break

        return compressed_data
    except Exception as e:
        logger.warning(f"Failed to compress image: {e}")
        return image_bytes  # Return original if compression fails


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
                    compressed_image = _compress_image(image)
                    upload = client.upload_blob(compressed_image)
                    blob_refs.append(models.AppBskyEmbedImages.Image(alt="Image", image=upload.blob))
                    logger.info(f"Uploaded image {i + 1}/{len(images)} to Bluesky")
                except Exception as e:
                    logger.error(f"Failed to upload image {i + 1} to Bluesky: {e}")
                    raise

        embed = None
        if blob_refs:
            embed = models.AppBskyEmbedImages.Main(images=blob_refs)

        client.send_post(text=text, embed=embed, langs=["ja"])
        logger.info("Successfully posted to Bluesky")

        # 他のサービス（Twitter, Misskey）と同様に辞書型で結果を返す
        return {"success": True}
    except Exception as e:
        logger.error(f"Failed to post to Bluesky: {type(e).__name__}: {e}", exc_info=True)
        raise
