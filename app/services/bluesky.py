import io
import logging
import re
from collections.abc import Mapping
from typing import Any, cast

import httpx
from atproto import Client, client_utils, models
from PIL import Image
from pydantic import BaseModel

from app.services.base import BlueskyAccount, ImageData, PostResult

logger = logging.getLogger(__name__)


class BlueskyService:
    PROVIDER_NAME = "bluesky"
    CHAR_LIMIT = 300

    def get_text_length(self, text: str) -> int:
        return len(text)

    def get_character_limit(self) -> int:
        return self.CHAR_LIMIT

    async def post(
        self,
        account: Mapping[str, Any],
        text: str,
        images: list[ImageData] | None = None,
        **kwargs: Any,
    ) -> PostResult:
        try:
            acc_model = BlueskyAccount.model_validate(account)
            resp = await post_to_bluesky(acc_model, text, images)
            # resp は models.ComAtprotoRepoCreateRecord.Response
            uri = getattr(resp, "uri", "")
            post_id = uri.split("/")[-1] if uri else None
            # Bluesky の Web URL 形式: https://bsky.app/profile/{handle}/post/{post_id}
            handle = acc_model.handle
            url = f"https://bsky.app/profile/{handle}/post/{post_id}" if handle and post_id else None

            return PostResult(
                success=True,
                provider=self.PROVIDER_NAME,
                post_id=post_id,
                url=url,
            )
        except Exception as e:
            logger.error(f"Bluesky post failed: {e}")
            return PostResult(success=False, provider=self.PROVIDER_NAME, error=str(e))


# リンク検出用のURLパターン
URL_PATTERN = re.compile(r"https?://[^\s]+")


def _compress_image(image_bytes: bytes, max_size: int = 975000) -> bytes:
    """
    画像を max_size バイト以下に圧縮します。
    Bluesky は約1MB（約976KB）の厳格な blob 制限があります。
    """
    if len(image_bytes) <= max_size:
        return image_bytes

    try:
        img = Image.open(io.BytesIO(image_bytes))

        # 必要に応じて RGB に変換（例：透明度のある PNG を JPEG に変換する場合など）
        if img.mode in ("RGBA", "P"):
            img = img.convert("RGB")

        # 最初の試行：高品質の JPEG に変換
        output = io.BytesIO()
        img.save(output, format="JPEG", quality=85)
        compressed_data = output.getvalue()

        if len(compressed_data) <= max_size:
            return compressed_data

        # まだ大きすぎる場合は、品質を下げてみる
        for quality in [70, 50, 30]:
            output = io.BytesIO()
            img.save(output, format="JPEG", quality=quality)
            compressed_data = output.getvalue()
            if len(compressed_data) <= max_size:
                return compressed_data

        # それでも大きすぎる場合は、リサイズする
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
        return image_bytes  # 圧縮に失敗した場合はオリジナルを返す


def _parse_urls(text: str) -> tuple[client_utils.TextBuilder, list[str]]:
    """
    テキストを解析して URL を検出し、それらのファセットを作成します。

    Returns:
        (ファセット付き TextBuilder, 見つかった URL のリスト) のタプル
    """
    builder = client_utils.TextBuilder()
    urls = []

    # URL パターンでテキストを分割
    parts = re.split(f"({URL_PATTERN.pattern})", text)

    for part in parts:
        if URL_PATTERN.match(part):
            # これが URL の場合、リンクファセットとして追加
            builder.link(part, part)
            urls.append(part)
        elif part:  # 空文字列をスキップ
            # これが通常のテキストの場合
            builder.text(part)

    return builder, urls


class BlueskyMetadata(BaseModel):
    title: str
    description: str
    image: str


async def _get_url_metadata(url: str) -> BlueskyMetadata | None:
    """
    HTML ページをスクレイピングして URL のメタデータを取得します。

    Returns:
        タイトル、説明、画像 URL を含む Pydantic モデル。失敗した場合は None。
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

            # Open Graph タグを優先し、次に通常の meta タグから取得を試みる
            title: str | None = None
            description: str | None = None
            image: str | None = None

            # タイトルの取得
            og_title = soup.find("meta", property="og:title")
            if og_title and og_title.get("content"):
                title = cast(str, og_title.get("content"))
            else:
                title_tag = soup.find("title")
                if title_tag:
                    title = title_tag.string

            # 説明の取得
            og_description = soup.find("meta", property="og:description")
            if og_description and og_description.get("content"):
                description = cast(str, og_description.get("content"))
            else:
                desc_tag = soup.find("meta", attrs={"name": "description"})
                if desc_tag and desc_tag.get("content"):
                    description = cast(str, desc_tag.get("content"))

            # 画像の取得
            og_image = soup.find("meta", property="og:image")
            if og_image and og_image.get("content"):
                image = cast(str, og_image.get("content"))

            # 画像 URL が絶対パスであることを確認
            if image and not image.startswith("http"):
                from urllib.parse import urljoin

                image = urljoin(url, image)

            desc_preview = description[:50] if description else None
            logger.info(f"Scraped metadata - Title: {title}, Description: {desc_preview}..., Image: {image}")

            return BlueskyMetadata(
                title=title or "",
                description=description or "",
                image=image or "",
            )
    except Exception as e:
        logger.warning(f"Failed to fetch metadata for {url}: {e}", exc_info=True)
        return None


async def _create_embed_card(url: str, client: Client) -> models.AppBskyEmbedExternal.Main | None:
    """
    指定された URL の外部リンク用埋め込みカードを作成します。

    Args:
        url: 埋め込みカードを作成する URL
        client: 認証済みの Bluesky クライアント

    Returns:
        外部リンク埋め込みモデル。失敗した場合は None。
    """
    try:
        logger.info(f"Starting embed card creation for: {url}")

        # URL メタデータの取得
        metadata = await _get_url_metadata(url)
        logger.info(f"Metadata retrieved: {metadata}")

        if not metadata or not metadata.title:
            logger.warning(f"No metadata found for {url}")
            return None

        # サムネイル画像があればダウンロードしてアップロード
        thumb = None
        if metadata.image:
            try:
                logger.info(f"Downloading thumbnail from: {metadata.image}")
                async with httpx.AsyncClient(follow_redirects=True) as http_client:
                    img_response = await http_client.get(metadata.image, timeout=10.0)
                    img_response.raise_for_status()
                    img_bytes = img_response.content
                    logger.info(f"Downloaded {len(img_bytes)} bytes")

                    # 必要に応じて画像を圧縮
                    compressed_img = _compress_image(img_bytes)
                    logger.info(f"Compressed to {len(compressed_img)} bytes")

                    # Bluesky にアップロード
                    upload = client.upload_blob(compressed_img)
                    thumb = upload.blob
                    logger.info(f"Successfully uploaded thumbnail for {url}")
            except Exception as e:
                logger.warning(f"Failed to upload thumbnail for {url}: {e}", exc_info=True)
        else:
            logger.info("No thumbnail image in metadata")

        # 外部リンク埋め込みの作成
        external = models.AppBskyEmbedExternal.External(
            uri=url,
            title=metadata.title,
            description=metadata.description,
            thumb=thumb,
        )

        embed_card = models.AppBskyEmbedExternal.Main(external=external)
        logger.info(f"Created embed card: {embed_card}")

        return embed_card

    except Exception as e:
        logger.error(f"Failed to create embed card for {url}: {e}", exc_info=True)
        return None


async def post_to_bluesky(
    account: BlueskyAccount, text: str, images: list[ImageData] | None = None
) -> models.ComAtprotoRepoCreateRecord.Response:
    """
    Bluesky に投稿します（オプションで画像付き）。

    テキスト内の URL は自動的にクリック可能なリンクに変換されます。
    画像が提供されていない場合、最初に見つかった URL がカードとして埋め込まれます。

    Args:
        account: ハンドル名とパスワードを含む BlueskyAccount オブジェクト
        text: 投稿テキスト
        images: (画像バイト, MIMEタイプ) のタプルのリスト（オプション）

    Returns:
        成功ステータスの辞書

    Raises:
        Exception: Bluesky API エラーが発生した場合
    """
    if images is None:
        images = []

    try:
        client = Client()
        client.login(account.handle, account.password)
        logger.info(f"Logged in to Bluesky as {account.handle}")

        # テキストから URL を解析してファセットを作成
        text_builder, urls = _parse_urls(text)
        facets = text_builder.build_facets()
        logger.info(f"Found {len(urls)} URLs in text: {urls}")

        # 画像をアップロード
        blob_refs: list[models.AppBskyEmbedImages.Image] = []
        if images:
            for i, (image_byte_data, _mime_type) in enumerate(images):
                try:
                    compressed_image = _compress_image(image_byte_data)
                    upload = client.upload_blob(compressed_image)
                    blob_refs.append(models.AppBskyEmbedImages.Image(alt="Image", image=upload.blob))
                    logger.info(f"Uploaded image {i + 1}/{len(images)} to Bluesky")
                except Exception as e:
                    logger.error(f"Failed to upload image {i + 1} to Bluesky: {e}")
                    raise

        # 埋め込みタイプを決定
        embed: models.AppBskyEmbedImages.Main | models.AppBskyEmbedExternal.Main | None = None
        if blob_refs:
            # 画像を優先
            logger.info("Creating image embed (images provided)")
            embed = models.AppBskyEmbedImages.Main(images=blob_refs)
        elif urls:
            # 画像がない場合、最初の URL の埋め込みカードを作成
            logger.info(f"No images provided. Creating embed card for first URL: {urls[0]}")
            embed = await _create_embed_card(urls[0], client)
            if embed:
                logger.info("Embed card created successfully")
            else:
                logger.warning("Embed card creation returned None")
        else:
            logger.info("No images or URLs found, no embed will be added")

        logger.info(f"Final embed value: {embed}")
        resp = client.send_post(text=text, embed=embed, facets=facets, langs=["ja"])
        logger.info("Successfully posted to Bluesky")

        return resp
    except Exception as e:
        logger.error(f"Failed to post to Bluesky: {type(e).__name__}: {e}", exc_info=True)
        raise
