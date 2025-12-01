import io
import logging
import re
from typing import Any

import httpx
from atproto import Client, client_utils, models
from PIL import Image

logger = logging.getLogger(__name__)

# URL pattern for detecting links
URL_PATTERN = re.compile(r"https?://[^\s]+")


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


def _parse_urls(text: str) -> tuple[client_utils.TextBuilder, list[str]]:
    """
    Parse text and detect URLs, creating facets for them.

    Returns:
        Tuple of (TextBuilder with facets, list of URLs found)
    """
    builder = client_utils.TextBuilder()
    urls = []

    # Split text by URL pattern
    parts = re.split(f"({URL_PATTERN.pattern})", text)

    for part in parts:
        if URL_PATTERN.match(part):
            # This is a URL, add it as a link facet
            builder.link(part, part)
            urls.append(part)
        elif part:  # Skip empty strings
            # This is regular text
            builder.text(part)

    return builder, urls


async def _get_url_metadata(url: str) -> dict[str, str] | None:
    """
    Fetch URL metadata by scraping the HTML page.

    Returns:
        Dict with title, description, and image URL, or None if failed
    """
    try:
        from bs4 import BeautifulSoup

        async with httpx.AsyncClient(follow_redirects=True) as client:
            response = await client.get(
                url,
                timeout=10.0,
                headers={"User-Agent": "Mozilla/5.0 (compatible; Blueskyclient/1.0; +https://bsky.app)"},
            )
            response.raise_for_status()

            soup = BeautifulSoup(response.text, "html.parser")

            # Try to get Open Graph tags first, then fall back to regular meta tags
            title = None
            description = None
            image = None

            # Get title
            og_title = soup.find("meta", property="og:title")
            if og_title and og_title.get("content"):
                title = og_title.get("content")
            else:
                title_tag = soup.find("title")
                if title_tag:
                    title = title_tag.string

            # Get description
            og_description = soup.find("meta", property="og:description")
            if og_description and og_description.get("content"):
                description = og_description.get("content")
            else:
                desc_tag = soup.find("meta", attrs={"name": "description"})
                if desc_tag and desc_tag.get("content"):
                    description = desc_tag.get("content")

            # Get image
            og_image = soup.find("meta", property="og:image")
            if og_image and og_image.get("content"):
                image = og_image.get("content")

            # Make sure image URL is absolute
            if image and not image.startswith("http"):
                from urllib.parse import urljoin

                image = urljoin(url, image)

            desc_preview = description[:50] if description else None
            logger.info(f"Scraped metadata - Title: {title}, Description: {desc_preview}..., Image: {image}")

            return {
                "title": title or "",
                "description": description or "",
                "image": image or "",
            }
    except Exception as e:
        logger.warning(f"Failed to fetch metadata for {url}: {e}", exc_info=True)
        return None


async def _create_embed_card(url: str, client: Client) -> models.AppBskyEmbedExternal.Main | None:
    """
    Create an external embed card for the given URL.

    Args:
        url: URL to create embed card for
        client: Authenticated Bluesky client

    Returns:
        External embed model or None if failed
    """
    try:
        logger.info(f"Starting embed card creation for: {url}")

        # Get URL metadata
        metadata = await _get_url_metadata(url)
        logger.info(f"Metadata retrieved: {metadata}")

        if not metadata or not metadata["title"]:
            logger.warning(f"No metadata found for {url}")
            return None

        # Download and upload thumbnail image if available
        thumb = None
        if metadata["image"]:
            try:
                logger.info(f"Downloading thumbnail from: {metadata['image']}")
                async with httpx.AsyncClient(follow_redirects=True) as http_client:
                    img_response = await http_client.get(metadata["image"], timeout=10.0)
                    img_response.raise_for_status()
                    img_bytes = img_response.content
                    logger.info(f"Downloaded {len(img_bytes)} bytes")

                    # Compress image if needed
                    compressed_img = _compress_image(img_bytes)
                    logger.info(f"Compressed to {len(compressed_img)} bytes")

                    # Upload to Bluesky
                    upload = client.upload_blob(compressed_img)
                    thumb = upload.blob
                    logger.info(f"Successfully uploaded thumbnail for {url}")
            except Exception as e:
                logger.warning(f"Failed to upload thumbnail for {url}: {e}", exc_info=True)
        else:
            logger.info("No thumbnail image in metadata")

        # Create external embed
        external = models.AppBskyEmbedExternal.External(
            uri=url,
            title=metadata["title"],
            description=metadata["description"],
            thumb=thumb,
        )

        embed_card = models.AppBskyEmbedExternal.Main(external=external)
        logger.info(f"Created embed card: {embed_card}")

        return embed_card

    except Exception as e:
        logger.error(f"Failed to create embed card for {url}: {e}", exc_info=True)
        return None


async def post_to_bluesky(account: dict[str, Any], text: str, images: list[bytes] | None = None) -> dict[str, Any]:
    """
    Post to Bluesky with optional images.

    URLs in the text will be automatically converted to clickable links.
    If no images are provided, the first URL found will be embedded as a card.

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

        # Parse URLs from text and create facets
        text_builder, urls = _parse_urls(text)
        facets = text_builder.build_facets()
        logger.info(f"Found {len(urls)} URLs in text: {urls}")

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

        # Determine embed type
        embed = None
        if blob_refs:
            # Images take priority
            logger.info("Creating image embed (images provided)")
            embed = models.AppBskyEmbedImages.Main(images=blob_refs)
        elif urls:
            # If no images, create embed card for the first URL
            logger.info(f"No images provided. Creating embed card for first URL: {urls[0]}")
            embed = await _create_embed_card(urls[0], client)
            if embed:
                logger.info("Embed card created successfully")
            else:
                logger.warning("Embed card creation returned None")
        else:
            logger.info("No images or URLs found, no embed will be added")

        logger.info(f"Final embed value: {embed}")
        client.send_post(text=text, embed=embed, facets=facets, langs=["ja"])
        logger.info("Successfully posted to Bluesky")

        # 他のサービス（Twitter, Misskey）と同様に辞書型で結果を返す
        return {"success": True}
    except Exception as e:
        logger.error(f"Failed to post to Bluesky: {type(e).__name__}: {e}", exc_info=True)
        raise
