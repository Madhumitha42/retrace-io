from __future__ import annotations
import math
import time
from datetime import datetime
from typing import Dict, Any, List
from app.text_matcher import calculate_text_similarity
from app.clip_matcher import calculate_clip_image_similarity, calculate_cross_modal_similarity
from app.database import to_public_lost, to_public_found
from app.ml_trainer import get_learned_weights
from app.vector_index import vector_index

Tuple_Location = tuple[float, str, float]
Tuple_Time = tuple[float, str]

def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Calculate the great circle distance between two points in meters using the Haversine formula.
    """
    R = 6371000.0  # Earth radius in meters
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (math.sin(dlat / 2.0) ** 2 +
         math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2.0) ** 2)
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
    return R * c

def calculate_location_score(lat1: float, lon1: float, lat2: float, lon2: float) -> Tuple_Location:
    """
    Calculate location proximity similarity score (0.0 to 100.0) and human-readable distance.
    """
    distance_meters = haversine_distance(lat1, lon1, lat2, lon2)

    if distance_meters <= 100:
        score = 100.0 - (distance_meters / 100.0) * 10.0
        label = f"{round(distance_meters, 1)} meters (Very Strong Proximity)"
    elif distance_meters <= 500:
        score = 90.0 - ((distance_meters - 100) / 400.0) * 15.0
        label = f"{round(distance_meters, 1)} meters (Moderate Proximity)"
    elif distance_meters <= 2000:
        score = 75.0 - ((distance_meters - 500) / 1500.0) * 25.0
        label = f"{round(distance_meters / 1000.0, 2)} km (Weaker Proximity)"
    else:
        dist_km = distance_meters / 1000.0
        score = max(0.0, 50.0 - (dist_km - 2.0) * 5.0)
        label = f"{round(dist_km, 2)} km (Low Proximity)"

    return round(score, 2), label, round(distance_meters, 1)

def calculate_time_score(time_str1: str, time_str2: str) -> Tuple_Time:
    """
    Calculate time proximity score (0.0 to 100.0) based on hours difference.
    """
    try:
        dt1 = datetime.fromisoformat(time_str1.replace('Z', '+00:00'))
        dt2 = datetime.fromisoformat(time_str2.replace('Z', '+00:00'))
        diff_hours = abs((dt1 - dt2).total_seconds()) / 3600.0

        if diff_hours <= 2.0:
            score = 100.0 - (diff_hours / 2.0) * 5.0
            label = f"{round(diff_hours * 60, 0)} mins apart (Immediate Window)"
        elif diff_hours <= 24.0:
            score = 95.0 - ((diff_hours - 2) / 22.0) * 20.0
            label = f"{round(diff_hours, 1)} hours apart (Same Day)"
        elif diff_hours <= 72.0:
            score = 75.0 - ((diff_hours - 24) / 48.0) * 35.0
            label = f"{round(diff_hours / 24.0, 1)} days apart"
        else:
            days = diff_hours / 24.0
            score = max(0.0, 40.0 - (days - 3) * 5.0)
            label = f"{round(days, 1)} days apart"

        return round(score, 2), label
    except Exception:
        return 70.0, "Compatible Timeframe (Estimated)"

def compute_item_match(lost_item: dict, found_item: dict, weights: dict = None, text_score_override: float = None) -> Dict[str, Any]:
    """
    Main Multi-Vector AI Matching Engine with CLIP Embeddings & Learned ML Weights.
    """
    if weights is None:
        weights = get_learned_weights()

    w_img = weights.get("image_weight", 0.35)
    w_txt = weights.get("text_weight", 0.30)
    w_loc = weights.get("location_weight", 0.15)
    w_time = weights.get("time_weight", 0.10)
    w_attr = weights.get("attribute_weight", 0.10)

    lost_text = f"{lost_item.get('title', '')}. {lost_item.get('description', '')}"
    found_text = f"{found_item.get('title', '')}. {found_item.get('description', '')} {found_item.get('public_notes', '')}"

    # 1. Text Semantic Similarity
    if text_score_override is not None:
        text_score = text_score_override
    else:
        text_score = calculate_text_similarity(lost_text, found_text)

    # 2. CLIP Image & Cross-Modal Similarity
    lost_has_img = bool(lost_item.get('image_url'))
    found_has_img = bool(found_item.get('image_url'))
    is_cross_modal = False

    if lost_has_img and found_has_img:
        img_score, is_estimated = calculate_clip_image_similarity(
            lost_item.get('image_url'),
            found_item.get('image_url'),
            text1=lost_text,
            text2=found_text
        )
    elif not lost_has_img and found_has_img:
        # Cross-Modal Match: Lost Item Text vs Found Item Photo
        is_cross_modal = True
        is_estimated = False
        img_score = calculate_cross_modal_similarity(
            text_description=lost_text,
            image_url=found_item.get('image_url'),
            image_context_text=found_text
        )
    elif lost_has_img and not found_has_img:
        # Cross-Modal Match: Found Item Text vs Lost Item Photo
        is_cross_modal = True
        is_estimated = False
        img_score = calculate_cross_modal_similarity(
            text_description=found_text,
            image_url=lost_item.get('image_url'),
            image_context_text=lost_text
        )
    else:
        # Neither has photo -> fallback text estimate
        img_score = text_score
        is_estimated = True

    # 3. Location Proximity
    loc_score, loc_label, dist_m = calculate_location_score(
        float(lost_item.get('latitude', 0.0)),
        float(lost_item.get('longitude', 0.0)),
        float(found_item.get('latitude', 0.0)),
        float(found_item.get('longitude', 0.0))
    )

    # 4. Time Proximity
    time_score, time_label = calculate_time_score(
        lost_item.get('lost_datetime', ''),
        found_item.get('found_datetime', '')
    )

    # 5. Attribute Match (Category & Color alignment)
    cat_match = 100.0 if lost_item.get('category', '').lower() == found_item.get('category', '').lower() else 50.0
    color_match = 100.0 if lost_item.get('primary_color', '').lower() in found_item.get('primary_color', '').lower() or found_item.get('primary_color', '').lower() in lost_item.get('primary_color', '').lower() else 60.0
    attr_score = round(0.5 * cat_match + 0.5 * color_match, 2)

    # Normalize weights
    total_w = w_img + w_txt + w_loc + w_time + w_attr
    if total_w > 0:
        w_img /= total_w
        w_txt /= total_w
        w_loc /= total_w
        w_time /= total_w
        w_attr /= total_w

    final_score = (
        img_score * w_img +
        text_score * w_txt +
        loc_score * w_loc +
        time_score * w_time +
        attr_score * w_attr
    )
    final_score = round(final_score, 1)

    # Classification
    if final_score >= 80.0:
        match_status = "High Potential Match"
        status_color = "emerald"
    elif final_score >= 60.0:
        match_status = "Moderate Match"
        status_color = "amber"
    else:
        match_status = "Low Confidence Match"
        status_color = "slate"

    # Natural Language Explainability Bullet Points
    explanations = []
    if is_cross_modal:
        explanations.append(f"⚡ Cross-Modal CLIP Match ({img_score}%): Lost text description matched directly against Found photo vector space.")
    elif is_estimated:
        explanations.append(f"🖼️ CLIP Visual Similarity ({img_score}% - Fallback): Visual semantic space estimated.")
    else:
        explanations.append(f"🖼️ CLIP Visual Embeddings ({img_score}%): Semantic visual feature embeddings compared.")

    explanations.append(f"📝 Semantic Text Similarity ({text_score}%): Description keyword alignment.")
    explanations.append(f"📍 Location Proximity ({loc_score}%): Reported locations are within {loc_label}.")
    explanations.append(f"🕒 Temporal Compatibility ({time_score}%): Reported {time_label}.")
    explanations.append(f"🏷️ Attribute Match ({attr_score}%): Category '{lost_item.get('category')}' & color '{lost_item.get('primary_color')}'.")

    return {
        "lost_item": to_public_lost(lost_item),
        "found_item": to_public_found(found_item),
        "final_score": final_score,
        "match_status": match_status,
        "status_color": status_color,
        "is_cross_modal": is_cross_modal,
        "breakdown": {
            "image_similarity": img_score,
            "text_similarity": text_score,
            "location_proximity": loc_score,
            "time_proximity": time_score,
            "attribute_similarity": attr_score,
            "characteristics_similarity": attr_score
        },
        "labels": {
            "location_label": loc_label,
            "time_label": time_label,
            "distance_meters": dist_m
        },
        "weights_used": {
            "image": round(w_img * 100),
            "text": round(w_txt * 100),
            "location": round(w_loc * 100),
            "time": round(w_time * 100),
            "attribute": round(w_attr * 100)
        },
        "explanations": explanations
    }

def run_two_stage_matching(
    query_item: dict,
    query_type: str,
    target_pool: List[dict],
    weights: dict = None,
    top_k_recall: int = 50,
    min_score_threshold: float = 10.0
) -> Dict[str, Any]:
    """
    Two-Stage Search Pipeline:
    Stage 1: Vector Candidate Generation (ANN Index recall of top ~50 candidates)
    Stage 2: Multi-Vector Re-ranking (Logistic Regression Scorer)
    Returns matches list with timing performance telemetry.
    """
    total_pool_size = len(target_pool)
    
    # Stage 1: Vector ANN Recall
    recalled_candidates, stage1_time_ms = vector_index.recall_candidates(
        query_item, query_type, target_pool, top_k=top_k_recall
    )
    
    # Stage 2: Multi-Vector Re-ranking
    start_stage2 = time.perf_counter()
    matches = []
    
    for candidate in recalled_candidates:
        lost = query_item if query_type == "lost" else candidate
        found = candidate if query_type == "lost" else query_item
        
        m = compute_item_match(lost, found, weights=weights)
        if m["final_score"] >= min_score_threshold:
            matches.append(m)
            
    matches.sort(key=lambda x: x["final_score"], reverse=True)
    stage2_time_ms = round((time.perf_counter() - start_stage2) * 1000.0, 3)
    
    return {
        "matches": matches,
        "telemetry": {
            "stage1_recall_time_ms": stage1_time_ms,
            "stage2_rerank_time_ms": stage2_time_ms,
            "total_search_time_ms": round(stage1_time_ms + stage2_time_ms, 3),
            "total_candidate_pool": total_pool_size,
            "recalled_candidates_count": len(recalled_candidates),
            "algorithm": "Two-Stage Vector Index (ANN Candidate Recall + Logistic Regression Re-ranker)"
        }
    }
