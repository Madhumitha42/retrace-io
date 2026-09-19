import os
import uuid
from typing import Optional
from contextlib import asynccontextmanager
from fastapi import FastAPI, File, UploadFile, Form, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.database import get_db_context, init_db, to_public_lost, to_public_found
from app.models import LostItemCreate, FoundItemCreate, MatchRequest, VerifyClaimRequest, ContradictionRequest
from app.matching_engine import compute_item_match, run_two_stage_matching
from app.clip_matcher import calculate_dhash if hasattr(app := None, 'x') else None
from app.vision_matcher import calculate_dhash
from app.verification_engine import verify_hidden_characteristic
from app.contradiction_detector import analyze_document_contradictions
from app.ml_trainer import train_ml_weights, get_evaluation_report, get_learned_weights
from app.vector_index import vector_index

@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    # Sync database items into two-stage vector index on startup
    with get_db_context() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM lost_items")
        lost_items = [dict(r) for r in cursor.fetchall()]
        cursor.execute("SELECT * FROM found_items")
        found_items = [dict(r) for r in cursor.fetchall()]
        vector_index.sync_database(lost_items, found_items)
    yield

app = FastAPI(
    title="Retrace.io API",
    description="Empirical ML search & multi-vector AI matching engine for lost & found items with CLIP embeddings, two-stage vector index, fraud protection, and document contradiction detection.",
    version="2.0.0",
    lifespan=lifespan
)

# CORS Middleware setup - Pinned to frontend origin
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
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
        "version": "2.0.0",
        "endpoints": [
            "/api/items/lost",
            "/api/items/found",
            "/api/match",
            "/api/ml/train-weights",
            "/api/ml/evaluation-report",
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

        # Update Vector Candidate Index
        cursor.execute("SELECT * FROM lost_items WHERE id = ?", (new_id,))
        new_item = dict(cursor.fetchone())
        vector_index.index_lost_item(new_item)
        
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

        # Update Vector Candidate Index
        cursor.execute("SELECT * FROM found_items WHERE id = ?", (new_id,))
        new_item = dict(cursor.fetchone())
        vector_index.index_found_item(new_item)
        
    return {"status": "success", "message": "Found item report registered", "item_id": new_id}

# ---------------------------------------------------------
# 2. AI Two-Stage Search & Matching Engine Endpoint
# ---------------------------------------------------------

@app.post("/api/match")
def run_ai_match(req: MatchRequest):
    weights_dict = req.weights.dict() if req.weights else get_learned_weights()

    with get_db_context() as conn:
        cursor = conn.cursor()

        if req.item_type == "lost":
            cursor.execute("SELECT * FROM lost_items WHERE id = ?", (req.item_id,))
            row = cursor.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="Lost item not found")
            query_item = dict(row)

            cursor.execute("SELECT * FROM found_items")
            target_pool = [dict(r) for r in cursor.fetchall()]

        else:
            cursor.execute("SELECT * FROM found_items WHERE id = ?", (req.item_id,))
            row = cursor.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="Found item not found")
            query_item = dict(row)

            cursor.execute("SELECT * FROM lost_items")
            target_pool = [dict(r) for r in cursor.fetchall()]

    # Run Two-Stage Retrieval Engine (ANN Candidate Recall + Logistic Regression Re-ranking)
    result = run_two_stage_matching(
        query_item=query_item,
        query_type=req.item_type,
        target_pool=target_pool,
        weights=weights_dict,
        min_score_threshold=req.min_score_threshold
    )

    return {
        "status": "success",
        "target_id": req.item_id,
        "target_type": req.item_type,
        "total_matches": len(result["matches"]),
        "matches": result["matches"],
        "telemetry": result["telemetry"]
    }

# ---------------------------------------------------------
# 3. Machine Learning Weight Fitting & Evaluation Endpoints
# ---------------------------------------------------------

@app.post("/api/ml/train-weights")
def train_weights_endpoint():
    report = train_ml_weights()
    return {
        "status": "success",
        "message": "Logistic Regression model fitted successfully on verification logs & benchmark pairs.",
        "report": report
    }

@app.get("/api/ml/evaluation-report")
def evaluation_report_endpoint():
    report = get_evaluation_report()
    return {
        "status": "success",
        "report": report
    }

# ---------------------------------------------------------
# 4. Fraud Protection / Verification Challenge Endpoint
# ---------------------------------------------------------

@app.post("/api/verify-claim")
def verify_claim(req: VerifyClaimRequest, request: Request):
    client_ip = request.client.host if (request.client and request.client.host) else "127.0.0.1"

    with get_db_context() as conn:
        cursor = conn.cursor()

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
# 5. AI Document Contradiction Detector Endpoint
# ---------------------------------------------------------

@app.post("/api/contradiction/detect")
def detect_contradictions(req: ContradictionRequest):
    docs = [{"title": d.title, "text": d.text} for d in req.documents]
    analysis = analyze_document_contradictions(docs)
    return {
        "status": "success",
        "result": analysis
    }
