import pytest
import math
from datetime import datetime, timedelta
from fastapi.testclient import TestClient

from app.main import app
from app.matching_engine import haversine_distance, calculate_time_score, compute_item_match, run_two_stage_matching
from app.verification_engine import verify_hidden_characteristic
from app.database import init_db
from app.ml_trainer import train_ml_weights, get_evaluation_report
from app.clip_matcher import calculate_cross_modal_similarity, get_text_embedding, get_image_embedding
from app.vector_index import vector_index

@pytest.fixture(autouse=True)
def setup_test_db():
    init_db()

def test_haversine_known_distance():
    london_lat, london_lon = 51.5074, -0.1278
    paris_lat, paris_lon = 48.8566, 2.3522
    dist = haversine_distance(london_lat, london_lon, paris_lat, paris_lon)
    assert math.isclose(dist, 343556, rel_tol=0.01)

def test_time_decay_boundaries():
    now = datetime.utcnow()
    t_now = now.isoformat()
    
    t_2h = (now - timedelta(hours=2)).isoformat()
    score_2h, _ = calculate_time_score(t_now, t_2h)
    assert 94.0 <= score_2h <= 96.0

    t_24h = (now - timedelta(hours=24)).isoformat()
    score_24h, _ = calculate_time_score(t_now, t_24h)
    assert 74.0 <= score_24h <= 76.0

    t_72h = (now - timedelta(hours=72)).isoformat()
    score_72h, _ = calculate_time_score(t_now, t_72h)
    assert 39.0 <= score_72h <= 41.0

def test_weight_normalization():
    lost = {
        "id": 1, "title": "Black Bag", "description": "Black bag", "category": "Bag",
        "primary_color": "Black", "location_name": "Library", "latitude": 12.9716,
        "longitude": 77.5946, "lost_datetime": "2026-09-18T14:00:00",
        "hidden_characteristic": "secret turtle", "owner_name": "Rohan", "owner_contact": "rohan@ex.com"
    }
    found = {
        "id": 1, "title": "Dark Backpack", "description": "Dark backpack", "category": "Bag",
        "primary_color": "Black", "location_name": "Block B", "latitude": 12.9718,
        "longitude": 77.5949, "found_datetime": "2026-09-18T15:00:00",
        "finder_name": "Desk", "finder_contact": "desk@ex.com", "public_notes": "notes"
    }
    
    unnormalized_weights = {
        "image_weight": 3.5,
        "text_weight": 3.0,
        "location_weight": 1.5,
        "time_weight": 1.0,
        "attribute_weight": 1.0
    }
    
    res = compute_item_match(lost, found, weights=unnormalized_weights)
    assert 0.0 <= res["final_score"] <= 100.0
    assert res["weights_used"]["image"] == 35

def test_verification_pass_and_fail():
    secret = "Blue keychain with turtle attached to zipper"
    
    pass_res = verify_hidden_characteristic(secret, "blue turtle keychain zipper")
    assert pass_res["verified"] is True
    assert pass_res["similarity_score"] >= 60.0

    fail_res = verify_hidden_characteristic(secret, "red dragon sticker on laptop")
    assert fail_res["verified"] is False
    assert fail_res["similarity_score"] < 60.0

def test_public_endpoints_do_not_leak_secrets():
    client = TestClient(app)

    resp_lost = client.get("/api/items/lost")
    assert resp_lost.status_code == 200
    lost_items = resp_lost.json()["data"]
    for item in lost_items:
        assert "hidden_characteristic" not in item
        assert "owner_contact" not in item

    resp_found = client.get("/api/items/found")
    assert resp_found.status_code == 200
    found_items = resp_found.json()["data"]
    for item in found_items:
        assert "finder_contact" not in item

    match_req = {
        "item_id": 1,
        "item_type": "lost",
        "min_score_threshold": 10.0
    }
    resp_match = client.post("/api/match", json=match_req)
    assert resp_match.status_code == 200
    matches = resp_match.json()["matches"]
    for m in matches:
        assert "hidden_characteristic" not in m["lost_item"]
        assert "owner_contact" not in m["lost_item"]
        assert "finder_contact" not in m["found_item"]

def test_ml_logistic_regression_training_and_evaluation():
    report = train_ml_weights()
    assert report["status"] == "trained"
    assert report["sample_size"] >= 300
    assert report["roc_auc"] >= 0.85
    assert report["precision_at_1"] >= 0.80
    assert report["mrr"] >= 0.75
    assert len(report["calibration_curve"]) == 5
    assert len(report["ablation_study"]) == 6

def test_clip_cross_modal_matching():
    text_desc = "Black College Bag with blue turtle keychain"
    found_img_url = "https://images.unsplash.com/photo-1553062407-98eeb64c6a62?auto=format&fit=crop&w=600&q=80"
    
    sim_score = calculate_cross_modal_similarity(text_desc, found_img_url, image_context_text="Dark backpack found near library")
    assert 40.0 <= sim_score <= 100.0

def test_two_stage_vector_index_retrieval():
    lost = {
        "id": 1, "title": "Black Bag", "description": "Black bag with blue bottle", "category": "Bag",
        "primary_color": "Black", "location_name": "Library", "latitude": 12.9716,
        "longitude": 77.5946, "lost_datetime": "2026-09-18T14:00:00"
    }
    found = {
        "id": 1, "title": "Dark Backpack", "description": "Dark backpack near block B", "category": "Bag",
        "primary_color": "Black", "location_name": "Block B", "latitude": 12.9718,
        "longitude": 77.5949, "found_datetime": "2026-09-18T15:00:00"
    }
    
    res = run_two_stage_matching(lost, "lost", [found], top_k_recall=10)
    assert len(res["matches"]) == 1
    assert "telemetry" in res
    assert res["telemetry"]["recalled_candidates_count"] >= 1
    assert "stage1_recall_time_ms" in res["telemetry"]

def test_ml_endpoints():
    client = TestClient(app)
    
    # POST /api/ml/train-weights
    res_train = client.post("/api/ml/train-weights")
    assert res_train.status_code == 200
    assert res_train.json()["status"] == "success"
    
    # GET /api/ml/evaluation-report
    res_eval = client.get("/api/ml/evaluation-report")
    assert res_eval.status_code == 200
    assert "roc_auc" in res_eval.json()["report"]
    assert "ablation_study" in res_eval.json()["report"]
