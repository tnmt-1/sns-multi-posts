import io
import logging

from PIL import Image

logger = logging.getLogger(__name__)


def compress_image(
    image_bytes: bytes,
    max_size_bytes: int = 900 * 1024,  # デフォルト 900KB (Blueskyの1MB制限を考慮)
    quality: int = 85,
) -> bytes:
    """画像を圧縮して、指定されたサイズ以下に収まるようにします。

    Args:
        image_bytes (bytes): 元の画像データ。
        max_size_bytes (int): 最大許容サイズ（バイト）。
        quality (int): JPEG圧縮品質。

    Returns:
        bytes: 圧縮後の画像データ。
    """
    if len(image_bytes) <= max_size_bytes:
        return image_bytes

    try:
        img = Image.open(io.BytesIO(image_bytes))
        # RGBAの場合はRGBに変換（JPEG保存用）
        if img.mode in ("RGBA", "P"):
            img = img.convert("RGB")

        output = io.BytesIO()
        img.save(output, format="JPEG", quality=quality, optimize=True)

        # まだ超えている場合は品質を下げたりリサイズしたりする
        step = 0
        while output.tell() > max_size_bytes and step < 5:
            step += 1
            quality -= 10
            if quality < 30:
                # サイズを半分にする
                width, height = img.size
                img = img.resize((width // 2, height // 2), Image.Resampling.LANCZOS)
                quality = 70

            output = io.BytesIO()
            img.save(output, format="JPEG", quality=quality, optimize=True)

        logger.info(f"Image compressed: {len(image_bytes)} -> {output.tell()} bytes")
        return output.getvalue()
    except Exception as e:
        logger.error(f"Image compression failed: {e}")
        return image_bytes
