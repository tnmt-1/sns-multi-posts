import io
import logging

from PIL import Image

logger = logging.getLogger(__name__)


def compress_image(
    image_bytes: bytes,
    max_size_bytes: int = 900 * 1024,  # デフォルト 900KB (Blueskyの1MB制限を考慮)
    quality: int = 85,
) -> bytes:
    """画像を圧縮して、指定されたファイルサイズ以下に収まるように最適化します。

    主に SNS 各社のファイルサイズ制限（例: Bluesky は 1MB 未満）を回避するために
    使用されます。JPEG 形式への変換、品質の段階的低下、および必要に応じて
    解像度の縮小を行い、目標サイズへの収束を図ります。

    Args:
        image_bytes (bytes): 圧縮対象の画像バイナリデータ。
        max_size_bytes (int): 許容される最大ファイルサイズ（バイト単位）。デフォルトは 900KB。
        quality (int): 初回の JPEG 圧縮品質 (0-100)。デフォルトは 85。

    Returns:
        bytes: 圧縮・最適化済みの画像バイナリデータ。
            元のデータが既に制限以下であれば、そのまま返されます。
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
