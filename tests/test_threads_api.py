from app.tools.threads_api import ThreadsPublishingTool


class FakeResponse:
    def __init__(self, payload, status_code=200):
        self._payload = payload
        self.status_code = status_code
        self.is_error = status_code >= 400

    def json(self):
        return self._payload


def test_threads_tool_uses_container_publish_and_permalink(monkeypatch):
    posts = []

    def fake_post(url, data, timeout):
        posts.append((url, data))
        return FakeResponse({"id": "container-1"} if url.endswith("/threads") else {"id": "post-1"})

    def fake_get(url, params, timeout):
        return FakeResponse({"id": "post-1", "permalink": "https://www.threads.com/@tester/post/abc"})

    monkeypatch.setattr("app.tools.threads_api.httpx.post", fake_post)
    monkeypatch.setattr("app.tools.threads_api.httpx.get", fake_get)
    tool = ThreadsPublishingTool("secret-token", "user-1")
    result = tool.publish_text("검증된 Threads 본문")

    assert posts[0][1]["media_type"] == "TEXT"
    assert posts[0][0] == "https://graph.threads.com/me/threads"
    assert posts[1][0] == "https://graph.threads.com/me/threads_publish"
    assert posts[1][1]["creation_id"] == "container-1"
    assert result["threads_post_id"] == "post-1"
    assert result["threads_permalink"].startswith("https://www.threads.com/")
