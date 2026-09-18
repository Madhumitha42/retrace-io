import re
from app.text_matcher import calculate_text_similarity

def verify_hidden_characteristic(stored_characteristic: str, claimant_input: str) -> dict:
    """
    Evaluates whether claimant's input matches the private hidden characteristic.
    Returns result dict with verified boolean, similarity score, and explanation.
    """
    if not stored_characteristic or not claimant_input:
        return {
            "verified": False,
            "similarity_score": 0.0,
            "message": "Missing characteristic information for verification challenge."
        }

    # Clean strings
    clean_stored = stored_characteristic.strip().lower()
    clean_input = claimant_input.strip().lower()

    # Direct substring / keyword check
    stored_words = set(re.findall(r'\b[a-z0-9]+\b', clean_stored))
    input_words = set(re.findall(r'\b[a-z0-9]+\b', clean_input))

    common = stored_words.intersection(input_words)
    keyword_overlap = len(common) / len(stored_words) if stored_words else 0.0

    # Semantic similarity check
    semantic_score = calculate_text_similarity(clean_stored, clean_input)

    # Combined score
    combined_score = max(keyword_overlap * 100.0, semantic_score)

    # Threshold for passing fraud challenge (60% confidence required)
    is_verified = combined_score >= 60.0

    if is_verified:
        message = "Verification Successful! Your description matches the private hidden detail."
    else:
        message = "Verification Failed. The description provided does not match the unpublicized characteristic."

    return {
        "verified": is_verified,
        "similarity_score": round(combined_score, 2),
        "message": message
    }
