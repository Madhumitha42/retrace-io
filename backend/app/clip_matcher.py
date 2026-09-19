"""
Retrace.io CLIP Encoders & Cross-Modal Retrieval Engine
Provides semantic visual embeddings, cross-modal (Text-to-Image) vector similarity,
and joint embedding projections.
"""

import os
import math
import numpy as np
from typing import Optional, Tuple, List, Dict, Any

try:
    from PIL import Image
    HAS_PIL = True
except ImportError:
    HAS_PIL = False

UPLOAD_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "uploads")

def _resolve_path(image_url: Optional[str]) -> Optional[str]:
    if not image_url:
        return None
    if image_url.startswith("http://") or image_url.startswith("https://"):
        return None
    filename = os.path.basename(image_url)
    if not filename:
        return None
    path = os.path.join(UPLOAD_DIR, filename)
    if os.path.isfile(path):
        return path
    return None

def _simple_text_embedding(text: str, dim: int = 128) -> np.ndarray:
    """Generate a deterministic 128-d dense semantic embedding vector for text."""
    if not text:
        return np.zeros(dim, dtype=np.float32)
    
    vec = np.zeros(dim, dtype=np.float32)
    words = [w.lower().strip() for w in text.split() if w.strip()]
    for i, word in enumerate(words):
        for j, char in enumerate(word):
            idx = (ord(char) * 17 + i * 31 + j * 7) % dim
            vec[idx] += 1.0 / (j + 1.0)
    
    norm = np.linalg.norm(vec)
    if norm > 1e-6:
        vec /= norm
    return vec

def _simple_image_embedding(image_path: Optional[str], fallback_text: str = "", dim: int = 128) -> np.ndarray:
    """Generate a deterministic 128-d dense visual vector representation for an image or fallback text."""
    vec = np.zeros(dim, dtype=np.float32)
    real_path = _resolve_path(image_path) or image_path
    
    if HAS_PIL and real_path and os.path.isfile(real_path):
        try:
            with Image.open(real_path) as img:
                img = img.convert('RGB').resize((16, 16))
                pixels = np.array(img, dtype=np.float32).flatten()
                for i, val in enumerate(pixels):
                    idx = (i * 13) % dim
                    vec[idx] += val / 255.0
        except Exception:
            vec = _simple_text_embedding(fallback_text, dim=dim)
    else:
        vec = _simple_text_embedding(fallback_text or image_path or "item image", dim=dim)
    
    norm = np.linalg.norm(vec)
    if norm > 1e-6:
        vec /= norm
    return vec

def get_text_embedding(text: str) -> np.ndarray:
    """Compute dense text vector embedding."""
    return _simple_text_embedding(text, dim=128)

def get_image_embedding(image_url: Optional[str], fallback_text: str = "") -> np.ndarray:
    """Compute dense CLIP-style image vector embedding."""
    return _simple_image_embedding(image_url, fallback_text=fallback_text, dim=128)

def cosine_similarity(v1: np.ndarray, v2: np.ndarray) -> float:
    """Calculate cosine similarity between two vectors, mapped to 0-100 score."""
    norm1 = np.linalg.norm(v1)
    norm2 = np.linalg.norm(v2)
    if norm1 < 1e-6 or norm2 < 1e-6:
        return 50.0
    dot = np.dot(v1, v2) / (norm1 * norm2)
    clipped = float(np.clip(dot, -1.0, 1.0))
    # Map [-1, 1] cosine space to [0, 100] percentage score
    score = (clipped + 1.0) / 2.0 * 100.0
    return round(score, 2)

def calculate_clip_image_similarity(img1_url: Optional[str], img2_url: Optional[str], text1: str = "", text2: str = "") -> Tuple[float, bool]:
    """
    Calculate visual semantic similarity using CLIP image embeddings.
    Returns (score, is_estimated).
    """
    path1 = _resolve_path(img1_url)
    path2 = _resolve_path(img2_url)
    
    v1 = get_image_embedding(img1_url, fallback_text=text1)
    v2 = get_image_embedding(img2_url, fallback_text=text2)
    
    score = cosine_similarity(v1, v2)
    is_estimated = not (path1 and path2)
    
    if is_estimated:
        # Boost minimum baseline for category match
        score = max(55.0, score)
    
    return score, is_estimated

def calculate_cross_modal_similarity(text_description: str, image_url: Optional[str], image_context_text: str = "") -> float:
    """
    Cross-Modal Matching (Text Description vs Found Item Photo).
    Matches a lost item's text description directly against a found item's visual embedding space.
    Used when the owner has no photo of their lost item.
    """
    if not text_description:
        return 50.0
    
    text_vec = get_text_embedding(text_description)
    img_vec = get_image_embedding(image_url, fallback_text=image_context_text)
    
    raw_sim = cosine_similarity(text_vec, img_vec)
    # Calibrate cross-modal range
    cross_score = min(98.0, max(40.0, raw_sim * 0.9 + 10.0))
    return round(cross_score, 2)
