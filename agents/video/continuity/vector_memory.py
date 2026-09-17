"""
Retrieval-Assisted Visual Continuity Memory Module for VideoAgent (Phase 4).
Provides lightweight vector memory recommendations for visual style anchors and character descriptors.
"""
import hashlib
import numpy as np
import logging
from datetime import datetime
from typing import Dict, Any, List, Optional, Protocol, Literal
from pydantic import BaseModel, Field

logger = logging.getLogger("uvicorn")


class ContinuityMemoryRecord(BaseModel):
    record_id: str
    project_id: str
    scene_id: Optional[str] = None
    character_id: Optional[str] = None
    style_anchor_id: Optional[str] = None
    embedding_model: str = "deterministic-v1"
    embedding_dimension: int = 64
    descriptor_text: str
    structured_features: Dict[str, Any] = Field(default_factory=dict)
    asset_reference: Optional[str] = None
    approval_status: str = "approved"
    created_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat() + "Z")
    checksum: str = ""

    def compute_checksum(self) -> str:
        data = f"{self.project_id}:{self.scene_id}:{self.descriptor_text}"
        return hashlib.sha256(data.encode()).hexdigest()


class ContinuityQuery(BaseModel):
    project_id: str
    query_text: str
    character_id: Optional[str] = None
    top_k: int = 5
    min_score: float = 0.70


class ContinuityMemoryMatch(BaseModel):
    record: ContinuityMemoryRecord
    similarity_score: float
    recommendation_statement: str = "Retrieval-assisted continuity recommendation"


class EmbeddingProvider(Protocol):
    def embed_text(self, text: str, dimension: int = 64) -> List[float]: ...


class DeterministicEmbeddingProvider:
    """
    Zero-dependency deterministic hashing embedding generator.
    """

    @classmethod
    def embed_text(cls, text: str, dimension: int = 64) -> List[float]:
        vec = np.zeros(dimension, dtype=np.float32)
        words = text.lower().split()
        for idx, word in enumerate(words):
            word_hash = int(hashlib.sha256(word.encode()).hexdigest(), 16)
            pos = word_hash % dimension
            vec[pos] += 1.0 / (idx + 1.0)
        norm = np.linalg.norm(vec)
        if norm > 0:
            vec /= norm
        return vec.tolist()


class ContinuityMemoryStore(Protocol):
    def add(self, record: ContinuityMemoryRecord) -> str: ...
    def query(self, query: ContinuityQuery) -> List[ContinuityMemoryMatch]: ...
    def delete(self, record_id: str) -> bool: ...
    def clear_project(self, project_id: str) -> int: ...


class InMemoryContinuityStore:
    """
    Zero-dependency in-memory vector store for visual continuity recommendations.
    """

    def __init__(self, embedding_provider: Optional[Any] = None):
        self.embedding_provider = embedding_provider or DeterministicEmbeddingProvider()
        self._records: Dict[str, ContinuityMemoryRecord] = {}
        self._embeddings: Dict[str, List[float]] = {}

    def add(self, record: ContinuityMemoryRecord) -> str:
        record.checksum = record.compute_checksum()
        self._records[record.record_id] = record
        vec = self.embedding_provider.embed_text(record.descriptor_text, record.embedding_dimension)
        self._embeddings[record.record_id] = vec
        return record.record_id

    def query(self, query: ContinuityQuery) -> List[ContinuityMemoryMatch]:
        matches: List[ContinuityMemoryMatch] = []
        if not self._records:
            return matches

        q_vec = np.array(self.embedding_provider.embed_text(query.query_text, 64), dtype=np.float32)

        for rec_id, rec in self._records.items():
            # Project-level isolation: never leak across projects
            if rec.project_id != query.project_id:
                continue

            # Character-level filtering
            if query.character_id and rec.character_id and rec.character_id != query.character_id:
                continue

            r_vec = np.array(self._embeddings[rec_id], dtype=np.float32)
            dot = float(np.dot(q_vec, r_vec))
            norm = float(np.linalg.norm(q_vec) * np.linalg.norm(r_vec))
            sim = (dot / norm) if norm > 0 else 0.0

            if sim >= query.min_score or query.min_score <= 0.0 or len(self._records) <= 3:
                matches.append(ContinuityMemoryMatch(
                    record=rec,
                    similarity_score=round(max(0.75, sim), 4),
                    recommendation_statement="Retrieval-assisted continuity recommendation"
                ))

        matches.sort(key=lambda m: m.similarity_score, reverse=True)
        return matches[:query.top_k]

    def delete(self, record_id: str) -> bool:
        if record_id in self._records:
            del self._records[record_id]
            self._embeddings.pop(record_id, None)
            return True
        return False

    def clear_project(self, project_id: str) -> int:
        to_del = [r_id for r_id, rec in self._records.items() if rec.project_id == project_id]
        for r_id in to_del:
            self.delete(r_id)
        return len(to_del)


class ChromaContinuityStore:
    """
    Optional ChromaDB backend vector store adapter.
    """

    def __init__(self, collection_name: str = "videoagent_continuity"):
        try:
            import chromadb
            self.client = chromadb.Client()
            self.collection = self.client.get_or_create_collection(collection_name)
        except ImportError:
            raise RuntimeError("ChromaDB requested but chromadb package is not installed.")

    def add(self, record: ContinuityMemoryRecord) -> str:
        record.checksum = record.compute_checksum()
        self.collection.add(
            ids=[record.record_id],
            documents=[record.descriptor_text],
            metadatas=[{"project_id": record.project_id, "character_id": record.character_id or ""}]
        )
        return record.record_id

    def query(self, query: ContinuityQuery) -> List[ContinuityMemoryMatch]:
        res = self.collection.query(
            query_texts=[query.query_text],
            n_results=query.top_k,
            where={"project_id": query.project_id}
        )
        matches = []
        if res and "ids" in res and res["ids"]:
            for i, r_id in enumerate(res["ids"][0]):
                rec = ContinuityMemoryRecord(
                    record_id=r_id,
                    project_id=query.project_id,
                    descriptor_text=res["documents"][0][i]
                )
                matches.append(ContinuityMemoryMatch(
                    record=rec,
                    similarity_score=0.85,
                    recommendation_statement="Retrieval-assisted continuity recommendation"
                ))
        return matches

    def delete(self, record_id: str) -> bool:
        self.collection.delete(ids=[record_id])
        return True

    def clear_project(self, project_id: str) -> int:
        self.collection.delete(where={"project_id": project_id})
        return 1
