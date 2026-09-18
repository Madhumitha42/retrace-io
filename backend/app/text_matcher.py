import re
import logging
from typing import List

logger = logging.getLogger("text_matcher")

# Try importing SentenceTransformers for deep semantic embeddings
try:
    from sentence_transformers import SentenceTransformer, util
    ST_MODEL = SentenceTransformer('all-MiniLM-L6-v2')
    HAS_SENTENCE_TRANSFORMERS = True
except Exception as e:
    ST_MODEL = None
    HAS_SENTENCE_TRANSFORMERS = False
    logger.warning("LOUD WARNING: sentence-transformers failed to import or load model (%s). System is running on the Jaccard synonym fallback.", e)
    print("⚠️ LOUD WARNING: sentence-transformers failed to import. System is running on the Jaccard synonym fallback.")

# Domain-specific synonym map for lost & found items
SYNONYM_GROUPS = [
    {"bag", "backpack", "knapsack", "satchel", "rucksack", "duffel", "purse", "tote"},
    {"bottle", "flask", "thermos", "container", "canteen", "water bottle", "hydration vessel"},
    {"phone", "mobile", "cellphone", "smartphone", "iphone", "android", "device"},
    {"laptop", "notebook", "macbook", "computer", "pc"},
    {"keys", "keychain", "keyring", "fob", "keyset"},
    {"wallet", "billfold", "purse", "pouch", "cardholder"},
    {"glasses", "spectacles", "sunglasses", "shades", "eyewear"},
    {"watch", "smartwatch", "chronometer", "timepiece"},
    {"earbuds", "headphones", "airpods", "headset", "earphones"},
    {"jacket", "coat", "hoodie", "sweater", "outerwear", "parka"},
    {"college", "campus", "university", "school", "library", "block"},
    {"black", "dark", "charcoal", "onyx", "jet-black"},
    {"blue", "navy", "cyan", "azure", "cobalt"},
    {"red", "crimson", "maroon", "scarlet"},
]

def preprocess_text(text: str) -> List[str]:
    """Tokenize and normalize text."""
    text = text.lower()
    tokens = re.findall(r'\b[a-z0-9]+\b', text)
    return tokens

def get_synonym_expanded_tokens(tokens: List[str]) -> set:
    """Expand token set using domain synonym clusters."""
    expanded = set(tokens)
    for token in tokens:
        for group in SYNONYM_GROUPS:
            if token in group:
                expanded.update(group)
    return expanded

def fallback_semantic_similarity(text1: str, text2: str) -> float:
    """
    Fallback semantic similarity algorithm using Jaccard + domain synonym expansion.
    Produces accurate semantic matching when heavy transformer weights are unavailable.
    """
    tokens1 = preprocess_text(text1)
    tokens2 = preprocess_text(text2)

    if not tokens1 or not tokens2:
        return 0.0

    exp1 = get_synonym_expanded_tokens(tokens1)
    exp2 = get_synonym_expanded_tokens(tokens2)

    intersection = exp1.intersection(exp2)
    union = exp1.union(exp2)

    jaccard = len(intersection) / len(union) if union else 0.0

    overlap_count = 0
    for t1 in tokens1:
        for t2 in tokens2:
            if t1 == t2:
                overlap_count += 1
            else:
                for group in SYNONYM_GROUPS:
                    if t1 in group and t2 in group:
                        overlap_count += 0.8
                        break

    term_score = min(1.0, (overlap_count * 2.0) / (len(tokens1) + len(tokens2)))
    combined = 0.5 * jaccard + 0.5 * term_score
    return round(combined * 100.0, 2)

def _rescale_cosine(cos_val: float) -> float:
    # MiniLM cosine similarities typically range between 0.2 (unrelated) and 1.0 (identical).
    # Rescaling with max(0.0, (cos - 0.2) / 0.8) * 100 spreads scores across 0-100% for better UI distinction.
    rescaled = max(0.0, (cos_val - 0.2) / 0.8) * 100.0
    return round(min(100.0, rescaled), 2)

def calculate_text_similarity(text1: str, text2: str) -> float:
    """Calculate semantic text similarity score (0.0 to 100.0)."""
    if not text1 or not text2:
        return 0.0

    if HAS_SENTENCE_TRANSFORMERS and ST_MODEL is not None:
        try:
            embeddings1 = ST_MODEL.encode(text1, convert_to_tensor=True)
            embeddings2 = ST_MODEL.encode(text2, convert_to_tensor=True)
            cosine_score = util.cos_sim(embeddings1, embeddings2).item()
            return _rescale_cosine(cosine_score)
        except Exception:
            pass

    return fallback_semantic_similarity(text1, text2)

def batch_calculate_text_similarities(target_text: str, candidate_texts: List[str]) -> List[float]:
    """
    Batch calculate text similarities for a single target text against multiple candidate texts.
    Encodes the target text ONCE, then batch-encodes all candidates in a single model call.
    """
    if not target_text or not candidate_texts:
        return [0.0] * len(candidate_texts)

    if HAS_SENTENCE_TRANSFORMERS and ST_MODEL is not None:
        try:
            target_emb = ST_MODEL.encode(target_text, convert_to_tensor=True)
            cand_embs = ST_MODEL.encode(candidate_texts, convert_to_tensor=True)
            cosine_scores = util.cos_sim(target_emb, cand_embs)[0]
            scores = []
            for cos in cosine_scores:
                scores.append(_rescale_cosine(cos.item()))
            return scores
        except Exception as e:
            logger.warning("Batch encoding failed (%s), falling back to individual scoring.", e)

    return [fallback_semantic_similarity(target_text, cand) for cand in candidate_texts]
