import httpx

from app.tools.naver_news import NaverNewsSearchTool
from app.agents.research_agent import _classify_source


def test_naver_response_parser_and_headers(monkeypatch):
    captured = {}

    def fake_get(url, **kwargs):
        captured["url"] = url
        captured.update(kwargs)
        request = httpx.Request("GET", url)
        return httpx.Response(
            200,
            request=request,
            json={
                "items": [
                    {
                        "title": "<b>AI</b> 뉴스",
                        "originallink": "https://example.com/article",
                        "link": "https://n.news.naver.com/test",
                        "description": "설명 &amp; 검증",
                        "pubDate": "Wed, 10 Sep 2026 09:00:00 +0900",
                    }
                ]
            },
        )

    monkeypatch.setattr(httpx, "get", fake_get)
    result = NaverNewsSearchTool("client", "secret").search("AI", display=10)
    assert captured["url"] == "https://openapi.naver.com/v1/search/news.json"
    assert captured["headers"]["X-Naver-Client-Id"] == "client"
    assert captured["headers"]["X-Naver-Client-Secret"] == "secret"
    assert result[0]["title"] == "AI 뉴스"
    assert result[0]["description"] == "설명 & 검증"


def test_google_news_redirect_is_not_misclassified_as_official():
    assert _classify_source("https://news.google.com/rss/articles/abc") == "news"
