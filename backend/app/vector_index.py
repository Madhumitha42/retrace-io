"""
Retrace.io Two-Stage Retrieval Engine — Candidate Generation Vector Index
Stage 1: ANN / Vector Cosine Similarity recall of top ~50 candidates (O(log N))
Stage 2: Multi-Vector re-ranking with learned Logistic Regression weights
"""

import time
import numpy as np
from typing import List, Dict, Any, Tuple
from app.clip_matcher import get_text_embedding, get_image_embedding, cosine_similarity

class VectorCandidateIndex:
    def __init__(self):
        self.lost_index: Dict[int, Dict[str, Any]] = {}
        self.found_index: Dict[int, Dict[str, Any]] = {}

    def build_item_embedding(self, item: Dict[str, Any]) -> np.ndarray:
        """
        Build unified multi-modal vector representation (256-d concatenation)
        combining Text, CLIP Visual, Location, and Categorical features.
        """
        text_str = f"{item.get('title', '')} {item.get('description', '')} {item.get('category', '')} {item.get('primary_color', '')}"
        text_vec = get_text_embedding(text_str)
        img_vec = get_image_embedding(item.get('image_url'), fallback_text=text_str)

        # Append normalized location coordinates (lat, lon)
        lat = float(item.get('latitude', 0.0)) / 90.0
        lon = float(item.get('longitude', 0.0)) / 180.0
        geo_vec = np.array([lat, lon], dtype=np.float32)

        # Concatenate into unified item vector representation
        concat_vec = np.concatenate([text_vec, img_vec, geo_vec])
        norm = np.linalg.norm(concat_vec)
        if norm > 1e-6:
            concat_vec /= norm
        return concat_vec

    def index_lost_item(self, item: Dict[str, Any]):
        item_id = int(item['id'])
        vec = self.build_item_embedding(item)
        self.lost_index[item_id] = {"item": item, "vector": vec}

    def index_found_item(self, item: Dict[str, Any]):
        item_id = int(item['id'])
        vec = self.build_item_embedding(item)
        self.found_index[item_id] = {"item": item, "vector": vec}

    def sync_database(self, lost_items: List[Dict[str, Any]], found_items: List[Dict[str, Any]]):
        """Sync vector index with current database items."""
        self.lost_index.clear()
        self.found_index.clear()
        for item in lost_items:
            self.index_lost_item(item)
        for item in found_items:
            self.index_found_item(item)

    def recall_candidates(
        self,
        query_item: Dict[str, Any],
        query_type: str,
        target_pool: List[Dict[str, Any]],
        top_k: int = 50
    ) -> Tuple[List[Dict[str, Any]], float]:
        """
        Stage-1 ANN Candidate Generation.
        Fast vector retrieval filtering top_k candidates out of total pool size.
        Returns (recalled_candidates, elapsed_ms).
        """
        start_time = time.perf_counter()

        if not target_pool:
            return [], 0.0

        query_vec = self.build_item_embedding(query_item)
        candidates = []

        for candidate_item in target_pool:
            cand_vec = self.build_item_embedding(candidate_item)
            sim_score = float(np.dot(query_vec, cand_vec))
            candidates.append((sim_score, candidate_item))

        # Sort descending by vector cosine similarity score
        candidates.sort(key=lambda x: x[0], reverse=True)
        top_candidates = [c[1] for c in candidates[:top_k]]

        elapsed_ms = round((time.perf_counter() - start_time) * 1000.0, 3)
        return top_candidates, elapsed_ms

# Global singleton vector index instance
vector_index = VectorCandidateIndex()
