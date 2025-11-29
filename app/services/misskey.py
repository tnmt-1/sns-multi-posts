import httpx


async def post_to_misskey(
    account: dict[str, str],
    text: str,
    images: list[bytes] | None = None,
    visibility: str = "public",
) -> dict[str, str]:
    if images is None:
        images = []
    instance = account['instance']
    token = account['token']

    file_ids = []
    if images:
        async with httpx.AsyncClient() as client:
            for image in images:
                # Upload to drive/files/create
                files = {'file': image}
                data = {'i': token}
                # httpx handles multipart if files is passed
                # But we also need 'i' (token) in the body.
                # Misskey API expects 'i' as a parameter.

                resp = await client.post(
                    f"https://{instance}/api/drive/files/create",
                    data=data,
                    files=files
                )
                resp.raise_for_status()
                file_ids.append(resp.json()['id'])

    url = f"https://{instance}/api/notes/create"
    payload = {
        "i": token,
        "text": text,
        "visibility": visibility,
    }
    if file_ids:
        payload["fileIds"] = file_ids

    async with httpx.AsyncClient() as client:
        resp = await client.post(url, json=payload)
        resp.raise_for_status()
        return resp.json()
