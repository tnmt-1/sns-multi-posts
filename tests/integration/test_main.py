from fastapi.testclient import TestClient


def test_should_display_index_page(client: TestClient):
    """
    トップページ（/）にアクセスした際、正しくHTMLが返され、アプリ名が含まれていることを検証します。
    """
    # Arrange: 特になし（TestClientを使用）

    # Act: ートパスへのGETリクエスト
    response = client.get("/")

    # Assert: ステータスコードと含まれるテキストの検証
    assert response.status_code == 200
    assert "SNS Multi-Post" in response.text
