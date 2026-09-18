import uvicorn
import os
import sys

# Add app directory to sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

if __name__ == "__main__":
    print("🚀 Launching AI Lost-and-Found Intelligence System Backend...")
    print("📍 Server running on http://127.0.0.1:8000")
    print("📑 Swagger API Documentation at http://127.0.0.1:8000/docs")
    uvicorn.run("app.main:app", host="127.0.0.1", port=8000, reload=True)
