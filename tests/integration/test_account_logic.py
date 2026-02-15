from unittest.mock import MagicMock, patch


def test_bluesky_login_updates_existing_account(client):
    """Bluesky で同じアカウントでログインした場合に情報が更新されることを確認"""
    # 1回目：アカウント追加
    with patch("app.routers.auth.Client") as mock_client:
        mock_instance = mock_client.return_value
        mock_instance.login.return_value = MagicMock(did="did:123", handle="user1", display_name="User 1")

        client.post("/auth/login/bluesky", data={"handle": "user1", "password": "pass"})

        # トップ画面で確認
        response = client.get("/")
        assert "User 1" in response.text

    # 2回目：同じアカウントで名前を変えてログイン
    with patch("app.routers.auth.Client") as mock_client:
        mock_instance = mock_client.return_value
        mock_instance.login.return_value = MagicMock(did="did:123", handle="user1", display_name="User 1 Updated")

        client.post("/auth/login/bluesky", data={"handle": "user1", "password": "pass"})

        response = client.get("/")
        assert "User 1 Updated" in response.text


def test_misskey_multiple_instances_handling(client):
    """Misskey で異なるインスタンスの同名ユーザーが別々に保存されることを確認"""
    # インスタンス1
    client.post("/auth/login/misskey", data={"instance": "io.example.com"})

    with patch("httpx.AsyncClient.post") as mock_post:
        mock_post.return_value = MagicMock(status_code=200)
        mock_post.return_value.json.return_value = {
            "ok": True,
            "token": "t1",
            "user": {"id": "uid", "username": "user", "name": "User IO"},
        }
        client.get("/auth/callback/misskey")

    # インスタンス2
    client.post("/auth/login/misskey", data={"instance": "design.example.com"})

    with patch("httpx.AsyncClient.post") as mock_post:
        mock_post.return_value = MagicMock(status_code=200)
        mock_post.return_value.json.return_value = {
            "ok": True,
            "token": "t2",
            "user": {"id": "uid", "username": "user", "name": "User Design"},
        }
        client.get("/auth/callback/misskey")

    response = client.get("/")
    assert "User IO" in response.text
    assert "@io.example.com" in response.text
    assert "User Design" in response.text
    assert "@design.example.com" in response.text


def test_disconnect_removes_correct_account(client):
    """識別子を使用して正しいアカウントが削除されることを確認"""
    # まず2つ登録する
    client.post("/auth/login/misskey", data={"instance": "inst1"})
    with patch("httpx.AsyncClient.post") as mock_post:
        mock_post.return_value = MagicMock(status_code=200)
        mock_post.return_value.json.return_value = {
            "ok": True,
            "token": "t1",
            "user": {"id": "id1", "username": "u1", "name": "User 1"},
        }
        client.get("/auth/callback/misskey")

    client.post("/auth/login/misskey", data={"instance": "inst2"})
    with patch("httpx.AsyncClient.post") as mock_post:
        mock_post.return_value = MagicMock(status_code=200)
        mock_post.return_value.json.return_value = {
            "ok": True,
            "token": "t2",
            "user": {"id": "id2", "username": "u2", "name": "User 2"},
        }
        client.get("/auth/callback/misskey")

    # 状態確認
    res = client.get("/")
    assert "User 1" in res.text
    assert "User 2" in res.text

    # id1@inst1 を削除
    client.get("/auth/disconnect/misskey/id1@inst1")

    res = client.get("/")
    assert "User 1" not in res.text
    assert "User 2" in res.text
