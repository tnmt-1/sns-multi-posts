from typing import Any

from atproto import Client, models


async def post_to_bluesky(account: dict[str, Any], text: str, images: list[bytes] | None = None) -> bool:
    if images is None:
        images = []
    client = Client()
    client.login(account["handle"], account["password"])

    # Upload images
    blob_refs = []
    if images:
        for image in images:
            upload = client.upload_blob(image)
            blob_refs.append(models.AppBskyEmbedImages.Image(alt="Image", image=upload.blob))

    embed = None
    if blob_refs:
        embed = models.AppBskyEmbedImages.Main(images=blob_refs)

    client.send_post(text=text, embed=embed)
    return True
