from agents.graph_rag import GraphRAG
from agents.youtube_researcher import YouTubeResearcher


class DummyDriver:
    def __init__(self, uri, auth=None):
        pass

    def session(self):
        class S:
            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

            def write_transaction(self, fn, *a, **k):
                return True

            def read_transaction(self, fn, *a, **k):
                return []

        return S()

    def close(self):
        pass


def test_graph_rag_ingest(monkeypatch):
    # monkeypatch the GraphDatabase.driver to return our dummy
    import agents.graph_rag as gr

    monkeypatch.setattr(
        gr,
        "GraphDatabase",
        type("GD", (), {"driver": lambda *a, **k: DummyDriver(*a, **k)}),
    )

    # construct GraphRAG and ingest
    g = GraphRAG(uri="neo4j://fake:7687", user="u", password="p")
    ok = g.ingest(
        [
            {
                "videoId": "v1",
                "title": "t",
                "description": "d",
                "channelTitle": "c",
                "publishedAt": "2025-01-01",
                "viewCount": 10,
                "durationSeconds": 60,
                "suggestedTags": ["tag1"],
            }
        ]
    )
    g.close()
    assert ok


def test_youtube_uses_graph_rag(monkeypatch):
    import agents.graph_rag as gr

    monkeypatch.setattr(
        gr,
        "GraphDatabase",
        type("GD", (), {"driver": lambda *a, **k: DummyDriver(*a, **k)}),
    )
    r = YouTubeResearcher(api_key="test", vector_db_url="neo4j://fake:7687")
    records = [
        {
            "videoId": "v1",
            "title": "t",
            "description": "d",
            "channelTitle": "c",
            "publishedAt": "2025-01-01",
            "viewCount": 10,
            "durationSeconds": 60,
            "suggestedTags": ["tag1"],
        }
    ]
    assert r.post_to_vector_db(records) is True
