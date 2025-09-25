"""GraphRAG agent for Neo4j

Small wrapper around the neo4j driver to ingest simple video records and
perform basic retrievals. The tests monkeypatch GraphDatabase.driver, so the
implementation can be fairly straightforward.
"""
from typing import List, Dict, Optional
import os
import logging
from neo4j import GraphDatabase, basic_auth

logger = logging.getLogger(__name__)


class GraphRAG:
    def __init__(self, uri: str = None, user: Optional[str] = None, password: Optional[str] = None):
        self.uri = uri or os.environ.get("NEO4J_URI")
        self.user = user or os.environ.get("NEO4J_USER")
        self.password = password or os.environ.get("NEO4J_PASSWORD")
        if not self.uri:
            raise RuntimeError("NEO4J_URI not configured for GraphRAG")
        self._driver = GraphDatabase.driver(self.uri, auth=basic_auth(self.user, self.password))

    def close(self):
        try:
            self._driver.close()
        except Exception:
            pass

    # Ingest a list of video records into the graph
    def ingest(self, records: List[Dict]) -> bool:
        if not records:
            return True
        with self._driver.session() as session:
            for r in records:
                try:
                    session.write_transaction(self._create_or_update_video, r)
                except Exception:
                    logger.exception("Failed to ingest record %s", r.get("videoId"))
                    return False
        return True

    @staticmethod
    def _create_or_update_video(tx, record: Dict):
        vid = record.get("videoId")
        title = record.get("title")
        desc = record.get("description")
        channel = record.get("channelTitle")
        published = record.get("publishedAt")
        view_count = int(record.get("viewCount") or 0)
        duration = int(record.get("durationSeconds") or record.get("duration") or 0)
        tags = record.get("suggestedTags") or []

        tx.run(
            "MERGE (v:Video {videoId: $vid}) "
            "SET v.title = $title, v.description = $desc, v.channel = $channel, v.publishedAt = $published, "
            "v.viewCount = $view_count, v.durationSeconds = $duration",
            vid=vid,
            title=title,
            desc=desc,
            channel=channel,
            published=published,
            view_count=view_count,
            duration=duration,
        )

        if channel:
            tx.run(
                "MERGE (c:Channel {name: $channel})\n"
                "MERGE (v:Video {videoId: $vid})\n"
                "MERGE (v)-[:POSTED_ON]->(c)",
                channel=channel,
                vid=vid,
            )

        for t in tags:
            tx.run(
                "MERGE (tg:Tag {name: $tag})\n"
                "MERGE (v:Video {videoId: $vid})\n"
                "MERGE (v)-[:TAGGED_WITH]->(tg)",
                tag=t,
                vid=vid,
            )

        # heuristic relationships
        tx.run(
            "MATCH (v:Video {videoId: $vid})<-[:POSTED_ON]-(c:Channel)<-[:POSTED_ON]-(other:Video) "
            "WHERE other.videoId <> $vid "
            "MERGE (v)-[r:RELATED_BY_CHANNEL]->(other)",
            vid=vid,
        )

        tx.run(
            "MATCH (v:Video {videoId: $vid})-[:TAGGED_WITH]->(tg:Tag)<-[:TAGGED_WITH]-(other:Video) "
            "WHERE other.videoId <> $vid "
            "MERGE (v)-[r:RELATED_BY_TAG]->(other)",
            vid=vid,
        )

    # Simple retrieval: given a text query, find videos by matching tags/title and expand via graph
    def query(self, query_text: str, top_k: int = 10) -> List[Dict]:
        tokens = [t.lower() for t in query_text.split() if len(t) >= 3]
        if not tokens:
            return []
        with self._driver.session() as session:
            results = session.read_transaction(self._query_tx, tokens, top_k)
        return results

    @staticmethod
    def _query_tx(tx, tokens: List[str], top_k: int):
        token_params = {f"t{i}": f"%{tokens[i]}%" for i in range(len(tokens))}
        query_parts = []
        for i in range(len(tokens)):
            query_parts.append(f"toLower(v.title) CONTAINS $t{i}")
        query = (
            "MATCH (v:Video) WHERE " + " OR ".join(query_parts) + " RETURN v LIMIT $limit"
        )
        params = {**token_params, "limit": top_k}
        res = tx.run(query, **params)
        out = []
        for r in res:
            v = r["v"]
            props = dict(v.items())
            out.append(props)
        return out