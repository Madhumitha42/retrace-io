# Retrace.io — AI Lost-and-Found Intelligence & Contradiction System

An AI-assisted matching web application built with FastAPI and vanilla JavaScript designed to reconcile incomplete and differently worded lost-and-found item reports, backed by fraud protection challenge verification and an AI Document Contradiction Detector.

---

## 🛠️ Architecture & Matching Engine

The matching engine calculates a **Multi-Vector Similarity Score** combining:

1. **🖼️ Vision Matcher**: Perceptual Difference Hashing (`dHash` via Pillow) precalculated at upload time + OpenCV HSV color histogram correlation.
2. **📝 Semantic Text Matcher**: Sentence Transformers (`all-MiniLM-L6-v2`) with cosine score calibration (`max(0.0, (cos - 0.2) / 0.8) * 100.0`), backed by a domain Jaccard + synonym expansion fallback.
3. **📍 Spatial Location Proximity**: Haversine distance formula with threshold scoring (0-100m, 100-500m, 500m-2km, >2km).
4. **🕒 Temporal Proximity**: Hours/days normalized decay window.
5. **🏷️ Attribute Match**: Category and primary color alignment.
6. **🚨 Fraud Protection**: Private hidden characteristic challenge-response verification with IP-based rate limiting (HTTP 429 after 3 failed attempts in 1 hour).

---

## 🔒 Security & Privacy Features

- **Zero Secret Leakage**: `hidden_characteristic`, `owner_contact`, and `finder_contact` are stripped from all public listing and matching API responses via safe column projections (`to_public_lost`, `to_public_found`). Contact details are unmasked **only** upon successful verification challenge.
- **Brute-Force Rate Limiting**: Verification attempts log client IP; 3 failed attempts within 1 hour trigger HTTP 429.
- **Upload File Validation**: Filenames use `uuid.uuid4().hex`, file extensions are strictly validated (`.jpg`, `.jpeg`, `.png`, `.webp`), and upload sizes are capped at 5 MB.

---

## 🚀 Running the Application

### 1. Backend Server (FastAPI)
```bash
cd backend
pip install -r requirements.txt
python run.py
```
- API Base URL: `http://127.0.0.1:8000`
- Interactive API Docs: `http://127.0.0.1:8000/docs`

### 2. Frontend Application (HTML5 / Vanilla JS)
Serve `frontend/` using any static web server:
```bash
cd frontend
python -m http.server 3000
```
Open `http://localhost:3000` in your web browser.

---

## 🧪 Running Automated Tests
Run the pytest test suite:
```bash
cd backend
pytest
```
