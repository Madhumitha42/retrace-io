import os
import uuid
import shutil
from typing import Optional
from datetime import timedelta
from contextlib import asynccontextmanager
from fastapi import FastAPI, File, UploadFile, Form, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.database import get_db_context, init_db, to_public_lost, to_public_found
from app.models import LostItemCreate, FoundItemCreate, MatchRequest, VerifyClaimRequest, ContradictionRequest
from app.matching_engine import compute_item_match
from app.text_matcher import batch_calculate_text_similarities
from app.vision_matcher import calculate_dhash
from app.verification_engine import verify_hidden_characteristic
from app.contradiction_detector import analyze_document_contradictions

@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield

app = FastAPI(
    title="Retrace.io API",
    description="Multidimensional AI matching engine for lost & found items with fraud protection and document contradiction detection.",
    version="1.0.0",
    lifespan=lifespan
)

# CORS Middleware setup - Pinned to frontend origin
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

UPLOAD_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)

ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
MAX_FILE_SIZE = 5 * 1024 * 1024  # 5 MB

app.mount("/uploads", StaticFiles(directory=UPLOAD_DIR), name="uploads")

@app.get("/")
def root():
    return {
        "status": "online",
        "service": "Retrace.io AI Intelligence Platform",
        "version": "1.0.0",
        "endpoints": [
            "/api/items/lost",
            "/api/items/found",
            "/api/match",
            "/api/verify-claim",
            "/api/contradiction/detect"
        ]
    }

# ---------------------------------------------------------
# 1. Lost & Found Items Endpoints
# ---------------------------------------------------------

@app.get("/api/items/lost")
def get_lost_items(search: Optional[str] = None, category: Optional[str] = None):
    with get_db_context() as conn:
        cursor = conn.cursor()
        query = "SELECT * FROM lost_items WHERE 1=1"
        params = []
        
        if category and category != "All":
            query += " AND category = ?"
            params.append(category)
            
        if search:
            query += " AND (title LIKE ? OR description LIKE ? OR location_name LIKE ?)"
            term = f"%{search}%"
            params.extend([term, term, term])
            
        query += " ORDER BY id DESC"
        cursor.execute(query, params)
        items = [to_public_lost(dict(row)) for row in cursor.fetchall()]
        return {"status": "success", "count": len(items), "data": items}

@app.get("/api/items/found")
def get_found_items(search: Optional[str] = None, category: Optional[str] = None):
    with get_db_context() as conn:
        cursor = conn.cursor()
        query = "SELECT * FROM found_items WHERE 1=1"
        params = []
        
        if category and category != "All":
            query += " AND category = ?"
            params.append(category)
            
        if search:
            query += " AND (title LIKE ? OR description LIKE ? OR location_name LIKE ?)"
            term = f"%{search}%"
            params.extend([term, term, term])
            
        query += " ORDER BY id DESC"
        cursor.execute(query, params)
        items = [to_public_found(dict(row)) for row in cursor.fetchall()]
        return {"status": "success", "count": len(items), "data": items}

@app.post("/api/items/lost")
async def create_lost_item(
    title: str = Form(...),
    description: str = Form(...),
    category: str = Form(...),
    primary_color: str = Form(...),
    location_name: str = Form(...),
    latitude: float = Form(...),
    longitude: float = Form(...),
    lost_datetime: str = Form(...),
    hidden_characteristic: str = Form(...),
    owner_name: str = Form(...),
    owner_contact: str = Form(...),
    image: Optional[UploadFile] = File(None)
):
    # Validate via Pydantic model
    LostItemCreate(
        title=title, description=description, category=category, primary_color=primary_color,
        location_name=location_name, latitude=latitude, longitude=longitude,
        lost_datetime=lost_datetime, hidden_characteristic=hidden_characteristic,
        owner_name=owner_name, owner_contact=owner_contact
    )

    image_url = None
    image_hash = None
    
    if image and image.filename:
        ext = os.path.splitext(image.filename)[1].lower()
        if ext not in ALLOWED_EXTENSIONS:
            raise HTTPException(status_code=400, detail=f"Invalid file extension '{ext}'. Allowed: .jpg, .jpeg, .png, .webp")
        
        contents = await image.read()
        if len(contents) > MAX_FILE_SIZE:
            raise HTTPException(status_code=400, detail="Uploaded file exceeds maximum limit of 5 MB.")

        filename = f"lost_{uuid.uuid4().hex}{ext}"
        filepath = os.path.join(UPLOAD_DIR, filename)
        with open(filepath, "wb") as buffer:
            buffer.write(contents)
        
        image_url = f"/uploads/{filename}"
        image_hash = calculate_dhash(filepath)

    with get_db_context() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO lost_items 
            (title, description, category, primary_color, location_name, latitude, longitude, lost_datetime, hidden_characteristic, owner_name, owner_contact, image_url, image_hash)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (title, description, category, primary_color, location_name, latitude, longitude, lost_datetime, hidden_characteristic, owner_name, owner_contact, image_url, image_hash))
        
        conn.commit()
        new_id = cursor.lastrowid
        
    return {"status": "success", "message": "Lost item report registered", "item_id": new_id}

@app.post("/api/items/found")
async def create_found_item(
    title: str = Form(...),
    description: str = Form(...),
    category: str = Form(...),
    primary_color: str = Form(...),
    location_name: str = Form(...),
    latitude: float = Form(...),
    longitude: float = Form(...),
    found_datetime: str = Form(...),
    finder_name: str = Form(...),
    finder_contact: str = Form(...),
    public_notes: Optional[str] = Form(""),
    image: Optional[UploadFile] = File(None)
):
    # Validate via Pydantic model
    FoundItemCreate(
        title=title, description=description, category=category, primary_color=primary_color,
        location_name=location_name, latitude=latitude, longitude=longitude,
        found_datetime=found_datetime, finder_name=finder_name, finder_contact=finder_contact,
        public_notes=public_notes
    )

    image_url = None
    image_hash = None
    
    if image and image.filename:
        ext = os.path.splitext(image.filename)[1].lower()
        if ext not in ALLOWED_EXTENSIONS:
            raise HTTPException(status_code=400, detail=f"Invalid file extension '{ext}'. Allowed: .jpg, .jpeg, .png, .webp")
        
        contents = await image.read()
        if len(contents) > MAX_FILE_SIZE:
            raise HTTPException(status_code=400, detail="Uploaded file exceeds maximum limit of 5 MB.")

        filename = f"found_{uuid.uuid4().hex}{ext}"
        filepath = os.path.join(UPLOAD_DIR, filename)
        with open(filepath, "wb") as buffer:
            buffer.write(contents)
        
        image_url = f"/uploads/{filename}"
        image_hash = calculate_dhash(filepath)

    with get_db_context() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO found_items 
            (title, description, category, primary_color, location_name, latitude, longitude, found_datetime, finder_name, finder_contact, image_url, image_hash, public_notes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (title, description, category, primary_color, location_name, latitude, longitude, found_datetime, finder_name, finder_contact, image_url, image_hash, public_notes))
        
        conn.commit()
        new_id = cursor.lastrowid
        
    return {"status": "success", "message": "Found item report registered", "item_id": new_id}

# ---------------------------------------------------------
# 2. AI Multi-Vector Matching Engine Endpoint
# ---------------------------------------------------------

@app.post("/api/match")
def run_ai_match(req: MatchRequest):
    weights_dict = req.weights.dict() if req.weights else None
    matches = []

    with get_db_context() as conn:
        cursor = conn.cursor()

        if req.item_type == "lost":
            cursor.execute("SELECT * FROM lost_items WHERE id = ?", (req.item_id,))
            lost_row = cursor.fetchone()
            if not lost_row:
                raise HTTPException(status_code=404, detail="Lost item not found")
            lost_item = dict(lost_row)

            target_lat = float(lost_item["latitude"])
            target_lon = float(lost_item["longitude"])
            target_time = lost_item["lost_datetime"]
            target_cat = lost_item["category"]

            # Pre-filter shortlist candidates in SQL (same category, bounding box +-0.5 deg, time +-7 days)
            cursor.execute("""
                SELECT * FROM found_items
                WHERE category = ?
                  AND latitude BETWEEN ? AND ?
                  AND longitude BETWEEN ? AND ?
                  AND datetime(found_datetime) BETWEEN datetime(?, '-7 days') AND datetime(?, '+7 days')
            """, (target_cat, target_lat - 0.5, target_lat + 0.5, target_lon - 0.5, target_lon + 0.5, target_time, target_time))
            
            candidate_rows = cursor.fetchall()

            # Fallback to broader category search if strict spatial/temporal pre-filter yields empty
            if not candidate_rows:
                cursor.execute("SELECT * FROM found_items WHERE category = ?", (target_cat,))
                candidate_rows = cursor.fetchall()
            if not candidate_rows:
                cursor.execute("SELECT * FROM found_items")
                candidate_rows = cursor.fetchall()

            candidates = [dict(r) for r in candidate_rows]
            
            # Batch calculate text similarities
            target_text = f"{lost_item.get('title', '')}. {lost_item.get('description', '')}"
            cand_texts = [f"{c.get('title', '')}. {c.get('description', '')} {c.get('public_notes', '')}" for c in candidates]
            text_scores = batch_calculate_text_similarities(target_text, cand_texts)

            for cand, txt_score in zip(candidates, text_scores):
                match_res = compute_item_match(lost_item, cand, weights_dict, text_score_override=txt_score)
                if match_res["final_score"] >= req.min_score_threshold:
                    matches.append(match_res)

        else:
            cursor.execute("SELECT * FROM found_items WHERE id = ?", (req.item_id,))
            found_row = cursor.fetchone()
            if not found_row:
                raise HTTPException(status_code=404, detail="Found item not found")
            found_item = dict(found_row)

            target_lat = float(found_item["latitude"])
            target_lon = float(found_item["longitude"])
            target_time = found_item["found_datetime"]
            target_cat = found_item["category"]

            # Pre-filter shortlist candidates in SQL
            cursor.execute("""
                SELECT * FROM lost_items
                WHERE category = ?
                  AND latitude BETWEEN ? AND ?
                  AND longitude BETWEEN ? AND ?
                  AND datetime(lost_datetime) BETWEEN datetime(?, '-7 days') AND datetime(?, '+7 days')
            """, (target_cat, target_lat - 0.5, target_lat + 0.5, target_lon - 0.5, target_lon + 0.5, target_time, target_time))
            
            candidate_rows = cursor.fetchall()

            if not candidate_rows:
                cursor.execute("SELECT * FROM lost_items WHERE category = ?", (target_cat,))
                candidate_rows = cursor.fetchall()
            if not candidate_rows:
                cursor.execute("SELECT * FROM lost_items")
                candidate_rows = cursor.fetchall()

            candidates = [dict(r) for r in candidate_rows]

            # Batch calculate text similarities
            target_text = f"{found_item.get('title', '')}. {found_item.get('description', '')} {found_item.get('public_notes', '')}"
            cand_texts = [f"{c.get('title', '')}. {c.get('description', '')}" for c in candidates]
            text_scores = batch_calculate_text_similarities(target_text, cand_texts)

            for cand, txt_score in zip(candidates, text_scores):
                match_res = compute_item_match(cand, found_item, weights_dict, text_score_override=txt_score)
                if match_res["final_score"] >= req.min_score_threshold:
                    matches.append(match_res)

    matches.sort(key=lambda x: x["final_score"], reverse=True)

    return {
        "status": "success",
        "target_id": req.item_id,
        "target_type": req.item_type,
        "total_matches": len(matches),
        "matches": matches
    }

# ---------------------------------------------------------
# 3. Fraud Protection / Verification Challenge Endpoint
# ---------------------------------------------------------

@app.post("/api/verify-claim")
def verify_claim(req: VerifyClaimRequest, request: Request):
    client_ip = request.client.host if (request.client and request.client.host) else "127.0.0.1"

    with get_db_context() as conn:
        cursor = conn.cursor()

        # Brute-force protection check (Max 3 failed attempts per lost_item_id per client IP in last hour)
        cursor.execute("""
            SELECT COUNT(*) FROM match_verifications
            WHERE lost_item_id = ? AND client_ip = ? AND is_verified = 0
              AND created_at >= datetime('now', '-1 hour')
        """, (req.lost_item_id, client_ip))
        failed_count = cursor.fetchone()[0]

        if failed_count >= 3:
            raise HTTPException(status_code=429, detail="Too many failed verification attempts for this item. Please try again after 1 hour.")

        cursor.execute("SELECT * FROM lost_items WHERE id = ?", (req.lost_item_id,))
        lost_row = cursor.fetchone()
        if not lost_row:
            raise HTTPException(status_code=404, detail="Lost item record not found.")

        lost_item = dict(lost_row)
        stored_hidden = lost_item.get("hidden_characteristic", "")

        eval_result = verify_hidden_characteristic(stored_hidden, req.claimed_characteristic)

        cursor.execute("""
            INSERT INTO match_verifications (lost_item_id, found_item_id, claimant_input, similarity_score, is_verified, client_ip)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (req.lost_item_id, req.found_item_id, req.claimed_characteristic, eval_result["similarity_score"], 1 if eval_result["verified"] else 0, client_ip))
        conn.commit()

        response_data = {
            "status": "success",
            "verified": eval_result["verified"],
            "similarity_score": eval_result["similarity_score"],
            "message": eval_result["message"]
        }

        if eval_result["verified"]:
            # Unmask contact details ONLY upon successful verification
            cursor.execute("SELECT finder_name, finder_contact, public_notes FROM found_items WHERE id = ?", (req.found_item_id,))
            found_row = cursor.fetchone()
            if found_row:
                found_info = dict(found_row)
                response_data["contact_info"] = {
                    "finder_name": found_info["finder_name"],
                    "finder_contact": found_info["finder_contact"],
                    "owner_name": lost_item["owner_name"],
                    "owner_contact": lost_item["owner_contact"],
                    "public_notes": found_info["public_notes"]
                }

        return response_data

# ---------------------------------------------------------
# 4. AI Document Contradiction Detector Endpoint
# ---------------------------------------------------------

@app.post("/api/contradiction/detect")
def detect_contradictions(req: ContradictionRequest):
    docs = [{"title": d.title, "text": d.text} for d in req.documents]
    analysis = analyze_document_contradictions(docs)
    return {
        "status": "success",
        "result": analysis
    }
