import pytest
import math
from datetime import datetime, timedelta
from fastapi.testclient import TestClient

from app.main import app
from app.matching_engine import haversine_distance, calculate_time_score, compute_item_match
from app.verification_engine import verify_hidden_characteristic
from app.database import init_db

@pytest.fixture(autouse=True)
def setup_test_db():
    init_db()

def test_haversine_known_distance():
    # London (51.5074, -0.1278) to Paris (48.8566, 2.3522) ~ 343,556 meters
    london_lat, london_lon = 51.5074, -0.1278
    paris_lat, paris_lon = 48.8566, 2.3522
    dist = haversine_distance(london_lat, london_lon, paris_lat, paris_lon)
    # Check within 1% of 343,556 meters
    assert math.isclose(dist, 343556, rel_tol=0.01)

def test_time_decay_boundaries():
    now = datetime.utcnow()
    t_now = now.isoformat()
    
    # 2 hours difference -> score ~95%
    t_2h = (now - timedelta(hours=2)).isoformat()
    score_2h, _ = calculate_time_score(t_now, t_2h)
    assert 94.0 <= score_2h <= 96.0

    # 24 hours difference -> score ~75%
    t_24h = (now - timedelta(hours=24)).isoformat()
    score_24h, _ = calculate_time_score(t_now, t_24h)
    assert 74.0 <= score_24h <= 76.0

    # 72 hours difference -> score ~40%
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
    
    # Unnormalized weights summing to 10.0 instead of 1.0
    unnormalized_weights = {
        "image_weight": 3.5,
        "text_weight": 3.0,
        "location_weight": 1.5,
        "time_weight": 1.0,
        "attribute_weight": 1.0
    }
    
    res = compute_item_match(lost, found, weights=unnormalized_weights)
    # Final score must remain bounded between 0 and 100
    assert 0.0 <= res["final_score"] <= 100.0
    assert res["weights_used"]["image"] == 35

def test_verification_pass_and_fail():
    secret = "Blue keychain with turtle attached to zipper"
    
    # Matching input -> pass
    pass_res = verify_hidden_characteristic(secret, "blue turtle keychain zipper")
    assert pass_res["verified"] is True
    assert pass_res["similarity_score"] >= 60.0

    # Wrong input -> fail
    fail_res = verify_hidden_characteristic(secret, "red dragon sticker on laptop")
    assert fail_res["verified"] is False
    assert fail_res["similarity_score"] < 60.0

def test_public_endpoints_do_not_leak_secrets():
    client = TestClient(app)

    # 1. Test GET /api/items/lost
    resp_lost = client.get("/api/items/lost")
    assert resp_lost.status_code == 200
    lost_items = resp_lost.json()["data"]
    for item in lost_items:
        assert "hidden_characteristic" not in item
        assert "owner_contact" not in item

    # 2. Test GET /api/items/found
    resp_found = client.get("/api/items/found")
    assert resp_found.status_code == 200
    found_items = resp_found.json()["data"]
    for item in found_items:
        assert "finder_contact" not in item

    # 3. Test POST /api/match
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
