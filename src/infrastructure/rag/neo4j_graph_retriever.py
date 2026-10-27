"""Infrastructure RAG Neo4j Graph Retriever - Truy xuất thực thể và quan hệ từ Neo4j.

Sử dụng thư viện `neo4j` Python Driver chính thức.
Không phụ thuộc cứng vào danh sách nhãn (Labels) hay loại quan hệ (Relationship Types) của CSDL.
"""

from __future__ import annotations

import json
import re
from typing import Any

from neo4j import Driver, GraphDatabase, NotificationMinimumSeverity
from neo4j.exceptions import Neo4jError

from src.application.rag_service import (
    GraphNode,
    GraphRelation,
    GraphSearchResult,
    KnowledgeGraphRetrieverPort,
)
from src.domain.ports import LoggerPort, NullLogger

# Các ký tự đặc biệt của Lucene cần escape khi gọi db.index.fulltext.queryNodes
_LUCENE_SPECIAL_RE = re.compile(r'([+\-&|!(){}\[\]^"~*?:\\/])')


def _escape_lucene(text: str) -> str:
    return _LUCENE_SPECIAL_RE.sub(r"\\\1", text.strip())


def _parse_metadata(raw: Any) -> dict[str, Any]:
    """Chuyển đổi thuộc tính metadata (chuỗi JSON hoặc dict) trên Node/Relationship về dict."""
    if not raw:
        return {}
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str):
        try:
            parsed = json.loads(raw)
            return parsed if isinstance(parsed, dict) else {}
        except ValueError:
            return {}
    return {}


class Neo4jKnowledgeGraphRetriever(KnowledgeGraphRetrieverPort):
    """Adapter truy xuất đồ thị con (Subgraph) từ Neo4j bằng neo4j Python Driver."""

    def __init__(
        self,
        uri: str = "neo4j://127.0.0.1:7687",
        user: str = "neo4j",
        password: str = "",
        database: str | None = None,
        fulltext_index_name: str = "entity_fulltext_idx",
        max_anchors_per_entity: int = 3,
        logger: LoggerPort | None = None,
    ):
        self.uri = uri
        self.user = user
        self.password = password
        self.database = database
        self.fulltext_index_name = fulltext_index_name
        self.max_anchors_per_entity = max_anchors_per_entity
        self.logger: LoggerPort = logger or NullLogger()
        self._driver: Driver | None = None

    def _get_driver(self) -> Driver:
        if self._driver is None:
            self._driver = GraphDatabase.driver(
                self.uri,
                auth=(self.user, self.password),
                notifications_min_severity=NotificationMinimumSeverity.OFF,
            )
        return self._driver

    def close(self) -> None:
        if self._driver is not None:
            self._driver.close()
            self._driver = None

    def search_subgraph(
        self,
        entities: list[str],
        hop_depth: int = 1,
        limit: int = 15,
    ) -> GraphSearchResult:
        """Tìm các nút thực thể khớp tên/từ khóa và mở rộng láng giềng 1-2 bước."""
        cleaned = [e.strip() for e in entities if e and e.strip()]
        if not cleaned:
            return GraphSearchResult()

        driver = self._get_driver()
        with driver.session(database=self.database) as session:
            # Bước 1: Tìm các nút thực thể gốc (anchors) cho từng từ khóa
            anchor_id_groups: list[list[str]] = []
            matched_nodes: list[GraphNode] = []
            seen_node_ids: set[str] = set()

            for entity_query in cleaned:
                anchors = self._find_anchors_for_query(session, entity_query)
                if anchors:
                    group_ids: list[str] = []
                    for item in anchors:
                        elem_id = item["elem_id"]
                        group_ids.append(elem_id)
                        if elem_id not in seen_node_ids:
                            seen_node_ids.add(elem_id)
                            matched_nodes.append(item["node"])
                    anchor_id_groups.append(group_ids)

            if not matched_nodes:
                return GraphSearchResult()

            all_anchor_ids = list(seen_node_ids)
            relations: list[GraphRelation] = []
            seen_rel_keys: set[tuple[str, str, str, str]] = set()

            # Bước 2: Nếu có từ 2 cụm thực thể trở lên, ưu tiên tìm đường đi ngắn nhất (1..2 bước) nối giữa các cụm khác nhau
            if len(anchor_id_groups) >= 2:
                for i in range(len(anchor_id_groups)):
                    for j in range(i + 1, len(anchor_id_groups)):
                        if len(relations) >= limit:
                            break
                        path_rels = session.execute_read(
                            self._tx_find_connecting_relations,
                            anchor_id_groups[i],
                            anchor_id_groups[j],
                            limit - len(relations),
                        )
                        for rel in path_rels:
                            key = (rel.source.name, rel.relation_type, rel.target.name, rel.chunk_id)
                            if key not in seen_rel_keys:
                                seen_rel_keys.add(key)
                                relations.append(rel)

            # Bước 3: Mở rộng các mối quan hệ xung quanh các thực thể gốc (1 bước hoặc 2 bước)
            remaining = max(0, limit - len(relations))
            if remaining > 0:
                neighbor_rels = session.execute_read(
                    self._tx_expand_neighborhood,
                    all_anchor_ids,
                    hop_depth,
                    remaining * 2,
                )
                for rel in neighbor_rels:
                    key = (rel.source.name, rel.relation_type, rel.target.name, rel.chunk_id)
                    if key not in seen_rel_keys:
                        seen_rel_keys.add(key)
                        relations.append(rel)
                        if len(relations) >= limit:
                            break

            return GraphSearchResult(
                matched_nodes=matched_nodes,
                relations=relations[:limit],
            )

    def _find_anchors_for_query(
        self,
        session: Any,
        query_text: str,
    ) -> list[dict[str, Any]]:
        """Tìm các nút khớp với từ khóa (ưu tiên Fulltext Index, tự động fallback sang CONTAINS nếu chưa tạo index)."""
        try:
            records = session.execute_read(
                self._tx_fulltext_search_nodes,
                self.fulltext_index_name,
                query_text,
                self.max_anchors_per_entity,
            )
            if records:
                return records
        except Neo4jError as exc:
            self.logger.debug(
                f"[GraphRAG] Fulltext index '{self.fulltext_index_name}' chưa sẵn sàng hoặc lỗi, chuyển sang tìm kiếm CONTAINS: {exc}"
            )

        return session.execute_read(
            self._tx_contains_search_nodes,
            query_text,
            self.max_anchors_per_entity,
        )

    @staticmethod
    def _tx_fulltext_search_nodes(
        tx: Any,
        index_name: str,
        query_text: str,
        top_k: int,
    ) -> list[dict[str, Any]]:
        escaped = _escape_lucene(query_text)
        if not escaped:
            return []
        # Ưu tiên khớp cụm chính xác hoặc khớp các từ khóa
        lucene_query = f'name:"{escaped}"^3 OR "{escaped}"^2 OR {escaped}'
        cypher = """
        CALL db.index.fulltext.queryNodes($index_name, $lucene_query) YIELD node, score
        WHERE node.name IS NOT NULL
        WITH node, score,
             CASE
                 WHEN toLower(node.name) = toLower($raw_query) THEN 100.0
                 WHEN toLower(node.name) CONTAINS toLower($raw_query) THEN 20.0
                 ELSE 0.0
             END AS exact_bonus,
             COUNT { (node)--() } AS degree
        ORDER BY (score + exact_bonus) DESC, degree DESC
        LIMIT $top_k
        RETURN elementId(node) AS elem_id,
               labels(node) AS labels,
               node.name AS name,
               coalesce(node.description, '') AS description,
               node.metadata AS metadata
        """
        result = tx.run(
            cypher,
            index_name=index_name,
            lucene_query=lucene_query,
            raw_query=query_text,
            top_k=top_k,
        )
        return [Neo4jKnowledgeGraphRetriever._record_to_anchor(r) for r in result]

    @staticmethod
    def _tx_contains_search_nodes(
        tx: Any,
        query_text: str,
        top_k: int,
    ) -> list[dict[str, Any]]:
        cypher = """
        MATCH (node)
        WHERE node.name IS NOT NULL
          AND toLower(node.name) CONTAINS toLower($raw_query)
        WITH node,
             CASE WHEN toLower(node.name) = toLower($raw_query) THEN 1 ELSE 0 END AS is_exact,
             COUNT { (node)--() } AS degree
        ORDER BY is_exact DESC, degree DESC, size(node.name) ASC
        LIMIT $top_k
        RETURN elementId(node) AS elem_id,
               labels(node) AS labels,
               node.name AS name,
               coalesce(node.description, '') AS description,
               node.metadata AS metadata
        """
        result = tx.run(cypher, raw_query=query_text, top_k=top_k)
        return [Neo4jKnowledgeGraphRetriever._record_to_anchor(r) for r in result]

    @staticmethod
    def _tx_find_connecting_relations(
        tx: Any,
        group_a_ids: list[str],
        group_b_ids: list[str],
        limit: int,
    ) -> list[GraphRelation]:
        """Tìm các cạnh nằm trên đường đi ngắn nhất (1..2 bước) nối giữa hai cụm thực thể khác nhau."""
        cypher = """
        MATCH (a) WHERE elementId(a) IN $group_a_ids
        MATCH (b) WHERE elementId(b) IN $group_b_ids AND elementId(a) <> elementId(b)
        MATCH p = allShortestPaths((a)-[*1..2]-(b))
        UNWIND relationships(p) AS r
        WITH DISTINCT r, startNode(r) AS src, endNode(r) AS dst
        LIMIT $limit
        RETURN labels(src) AS src_labels,
               coalesce(src.name, '') AS src_name,
               coalesce(src.description, '') AS src_desc,
               src.metadata AS src_meta,
               type(r) AS rel_type,
               coalesce(r.evidence, '') AS evidence,
               coalesce(r.chunk_id, '') AS chunk_id,
               r.metadata AS rel_meta,
               labels(dst) AS dst_labels,
               coalesce(dst.name, '') AS dst_name,
               coalesce(dst.description, '') AS dst_desc,
               dst.metadata AS dst_meta
        """
        result = tx.run(
            cypher,
            group_a_ids=group_a_ids,
            group_b_ids=group_b_ids,
            limit=limit,
        )
        return [Neo4jKnowledgeGraphRetriever._record_to_relation(r) for r in result]

    @staticmethod
    def _tx_expand_neighborhood(
        tx: Any,
        anchor_ids: list[str],
        hop_depth: int,
        limit: int,
    ) -> list[GraphRelation]:
        """Mở rộng láng giềng 1 bước hoặc 2 bước xung quanh các thực thể gốc."""
        if hop_depth >= 2:
            cypher = """
            MATCH (a) WHERE elementId(a) IN $anchor_ids
            MATCH p = (a)-[*1..2]-(b)
            UNWIND relationships(p) AS r
            WITH DISTINCT r, startNode(r) AS src, endNode(r) AS dst,
                 CASE WHEN elementId(startNode(r)) IN $anchor_ids OR elementId(endNode(r)) IN $anchor_ids THEN 1 ELSE 2 END AS hop_order
            ORDER BY hop_order ASC
            LIMIT $limit
            RETURN labels(src) AS src_labels,
                   coalesce(src.name, '') AS src_name,
                   coalesce(src.description, '') AS src_desc,
                   src.metadata AS src_meta,
                   type(r) AS rel_type,
                   coalesce(r.evidence, '') AS evidence,
                   coalesce(r.chunk_id, '') AS chunk_id,
                   r.metadata AS rel_meta,
                   labels(dst) AS dst_labels,
                   coalesce(dst.name, '') AS dst_name,
                   coalesce(dst.description, '') AS dst_desc,
                   dst.metadata AS dst_meta
            """
        else:
            cypher = """
            MATCH (a) WHERE elementId(a) IN $anchor_ids
            MATCH (a)-[r]-(b)
            WITH DISTINCT r, startNode(r) AS src, endNode(r) AS dst
            LIMIT $limit
            RETURN labels(src) AS src_labels,
                   coalesce(src.name, '') AS src_name,
                   coalesce(src.description, '') AS src_desc,
                   src.metadata AS src_meta,
                   type(r) AS rel_type,
                   coalesce(r.evidence, '') AS evidence,
                   coalesce(r.chunk_id, '') AS chunk_id,
                   r.metadata AS rel_meta,
                   labels(dst) AS dst_labels,
                   coalesce(dst.name, '') AS dst_name,
                   coalesce(dst.description, '') AS dst_desc,
                   dst.metadata AS dst_meta
            """
        result = tx.run(cypher, anchor_ids=anchor_ids, limit=limit)
        return [Neo4jKnowledgeGraphRetriever._record_to_relation(r) for r in result]

    @staticmethod
    def _record_to_anchor(record: Any) -> dict[str, Any]:
        return {
            "elem_id": record["elem_id"],
            "node": GraphNode(
                name=record["name"],
                labels=list(record["labels"] or []),
                description=record["description"] or "",
                metadata=_parse_metadata(record["metadata"]),
            ),
        }

    @staticmethod
    def _record_to_relation(record: Any) -> GraphRelation:
        src = GraphNode(
            name=record["src_name"],
            labels=list(record["src_labels"] or []),
            description=record["src_desc"] or "",
            metadata=_parse_metadata(record["src_meta"]),
        )
        dst = GraphNode(
            name=record["dst_name"],
            labels=list(record["dst_labels"] or []),
            description=record["dst_desc"] or "",
            metadata=_parse_metadata(record["dst_meta"]),
        )
        return GraphRelation(
            source=src,
            relation_type=record["rel_type"] or "",
            target=dst,
            evidence=record["evidence"] or "",
            chunk_id=record["chunk_id"] or "",
            metadata=_parse_metadata(record["rel_meta"]),
        )
