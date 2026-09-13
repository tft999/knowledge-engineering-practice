"""Deterministic vector, hybrid and graph-expanded retrieval."""

import hashlib
import math
import re
from collections import defaultdict
from typing import Protocol

import networkx as nx

from cookkg.evidence import Evidence, RetrieverName

RETRIEVER_NAMES: tuple[RetrieverName, ...] = (
    "vector",
    "vector_cypher",
    "hybrid",
    "hybrid_cypher",
)


class Retriever(Protocol):
    def search(self, query: str, top_k: int = 5) -> list[Evidence]: ...


def _tokens(text: str) -> list[str]:
    normalized = re.sub(r"\s+", "", text.lower())
    words = re.findall(r"[a-z0-9]+|[\u4e00-\u9fff]", normalized)
    cjk = "".join(token for token in words if len(token) == 1 and "\u4e00" <= token <= "\u9fff")
    grams = [cjk[index : index + 2] for index in range(max(0, len(cjk) - 1))]
    return [*words, *grams]


class HashingEmbedder:
    """Offline deterministic embedding used in tests and no-network demos."""

    def __init__(self, dimensions: int = 128):
        self.dimensions = dimensions

    def embed(self, text: str) -> list[float]:
        vector = [0.0] * self.dimensions
        for token in _tokens(text):
            digest = hashlib.sha256(token.encode("utf-8")).digest()
            index = int.from_bytes(digest[:4], "big") % self.dimensions
            sign = 1.0 if digest[4] % 2 == 0 else -1.0
            vector[index] += sign
        length = math.sqrt(sum(value * value for value in vector)) or 1.0
        return [value / length for value in vector]


def _cosine(left: list[float], right: list[float]) -> float:
    return sum(a * b for a, b in zip(left, right, strict=True))


def _copy(item: Evidence, score: float, retriever: RetrieverName) -> Evidence:
    return item.model_copy(update={"score": float(score), "retriever": retriever})


class VectorRetriever:
    name: RetrieverName = "vector"

    def __init__(self, evidence: list[Evidence], embedder: HashingEmbedder | None = None):
        self.evidence = list(evidence)
        self.embedder = embedder or HashingEmbedder()
        self.vectors = {item.evidence_id: self.embedder.embed(item.text) for item in evidence}

    def search(self, query: str, top_k: int = 5) -> list[Evidence]:
        if top_k < 1 or not query.strip():
            return []
        query_vector = self.embedder.embed(query)
        scored = [
            _copy(item, _cosine(query_vector, self.vectors[item.evidence_id]), self.name)
            for item in self.evidence
        ]
        return sorted(scored, key=lambda item: (-item.score, item.evidence_id))[:top_k]


class KeywordRetriever:
    def __init__(self, evidence: list[Evidence]):
        self.evidence = list(evidence)

    def search(self, query: str, top_k: int) -> list[tuple[Evidence, float]]:
        query_tokens = set(_tokens(query))
        scored = []
        for item in self.evidence:
            text_tokens = set(_tokens(item.text))
            overlap = len(query_tokens & text_tokens)
            phrase_bonus = 2 if query.strip() and query.strip() in item.text else 0
            score = overlap + phrase_bonus
            if score:
                scored.append((item, float(score)))
        return sorted(scored, key=lambda pair: (-pair[1], pair[0].evidence_id))[:top_k]


class HybridRetriever:
    name: RetrieverName = "hybrid"

    def __init__(self, evidence: list[Evidence], embedder: HashingEmbedder | None = None):
        self.vector = VectorRetriever(evidence, embedder)
        self.keyword = KeywordRetriever(evidence)

    def search(self, query: str, top_k: int = 5) -> list[Evidence]:
        if top_k < 1:
            return []
        depth = max(top_k * 4, 10)
        vector = self.vector.search(query, depth)
        keyword = self.keyword.search(query, depth)
        by_id: dict[str, Evidence] = {}
        scores: defaultdict[str, float] = defaultdict(float)
        for rank, item in enumerate(vector, 1):
            by_id[item.evidence_id] = item
            scores[item.evidence_id] += 1 / (60 + rank)
        for rank, (item, _) in enumerate(keyword, 1):
            by_id[item.evidence_id] = item
            scores[item.evidence_id] += 1 / (60 + rank)
        result = [_copy(by_id[item_id], score, self.name) for item_id, score in scores.items()]
        return sorted(result, key=lambda item: (-item.score, item.evidence_id))[:top_k]


class NetworkXGraphExpander:
    """Offline equivalent of the controlled recipe-ingredient Cypher expansion."""

    def __init__(self, graph: nx.DiGraph):
        self.graph = graph

    def related_recipe_ids(self, recipe_ids: set[str]) -> set[str]:
        related = set(recipe_ids)
        for recipe_id in sorted(recipe_ids):
            node = f"r:{recipe_id}"
            if node not in self.graph:
                continue
            ingredients = [
                target
                for _, target, edge in self.graph.out_edges(node, data=True)
                if self.graph.nodes[target].get("kind") == "ingredient"
                and edge.get("relation") in {"REQUIRES", "OPTIONALLY_USES", "ONE_OF"}
            ]
            for ingredient in ingredients:
                for source in self.graph.predecessors(ingredient):
                    attrs = self.graph.nodes[source]
                    if attrs.get("kind") == "recipe" and attrs.get("reviewed"):
                        related.add(attrs["id"])
        return related


class Neo4jCypherExpander:
    """Run one fixed, parameterized recipe→ingredient←recipe expansion."""

    QUERY = """
    UNWIND $recipe_ids AS recipe_id
    MATCH (seed:CookKGRecipe {id: recipe_id})-[seed_edge]->(ingredient:CookKGIngredient)
    MATCH (related:CookKGRecipe)-[related_edge]->(ingredient)
    WHERE type(seed_edge) IN ['COOKKG_REQUIRES', 'COOKKG_OPTIONALLY_USES']
      AND type(related_edge) IN ['COOKKG_REQUIRES', 'COOKKG_OPTIONALLY_USES']
      AND seed.dataset = $dataset AND seed.source_commit = $source_commit
      AND related.dataset = $dataset AND related.source_commit = $source_commit
    RETURN DISTINCT related.id AS recipe_id
    ORDER BY recipe_id
    """

    def __init__(self, session_factory, dataset: str, source_commit: str):
        self.session_factory = session_factory
        self.dataset = dataset
        self.source_commit = source_commit

    def related_recipe_ids(self, recipe_ids: set[str]) -> set[str]:
        related = set(recipe_ids)
        if not recipe_ids:
            return related
        session_or_context = (
            self.session_factory()
            if callable(self.session_factory)
            else self.session_factory
        )
        if hasattr(session_or_context, "__enter__"):
            with session_or_context as session:
                rows = list(self._run(session, recipe_ids))
        else:
            rows = list(self._run(session_or_context, recipe_ids))
        related.update(row["recipe_id"] for row in rows)
        return related

    def _run(self, session, recipe_ids: set[str]):
        return session.run(
            self.QUERY,
            recipe_ids=sorted(recipe_ids),
            dataset=self.dataset,
            source_commit=self.source_commit,
        )


class GraphExpandedRetriever:
    def __init__(
        self,
        base: Retriever,
        evidence: list[Evidence],
        graph: nx.DiGraph,
        name: RetrieverName,
        expander=None,
    ):
        self.base = base
        self.evidence = list(evidence)
        self.expander = expander or NetworkXGraphExpander(graph)
        self.name = name

    def search(self, query: str, top_k: int = 5) -> list[Evidence]:
        if top_k < 1:
            return []
        seeds = self.base.search(query, max(top_k, 5))
        if not seeds:
            return []
        seed_score = {item.evidence_id: item.score for item in seeds}
        recipe_ids = self.expander.related_recipe_ids({item.recipe_id for item in seeds})
        candidates = []
        for item in self.evidence:
            if item.recipe_id not in recipe_ids:
                continue
            score = seed_score.get(item.evidence_id, 0.0) + 0.001
            candidates.append(_copy(item, score, self.name))
        return sorted(candidates, key=lambda item: (-item.score, item.evidence_id))[:top_k]


def build_retrievers(
    evidence: list[Evidence], graph: nx.DiGraph, graph_expander=None
) -> dict[RetrieverName, Retriever]:
    vector = VectorRetriever(evidence)
    hybrid = HybridRetriever(evidence)
    return {
        "vector": vector,
        "vector_cypher": GraphExpandedRetriever(
            vector, evidence, graph, "vector_cypher", graph_expander
        ),
        "hybrid": hybrid,
        "hybrid_cypher": GraphExpandedRetriever(
            hybrid, evidence, graph, "hybrid_cypher", graph_expander
        ),
    }
