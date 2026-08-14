import os
import sys
from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

# Ensure root directory and backend directory are in sys.path
current_dir = Path(__file__).resolve().parent
backend_dir = current_dir.parent
root_dir = backend_dir.parent

for p in [str(root_dir), str(backend_dir)]:
    if p not in sys.path:
        sys.path.insert(0, p)

from .database import engine, Base
from .routers import auth, dashboard, documents

# Load environment variables
dotenv_path = root_dir / ".env"
if os.path.exists(dotenv_path):
    load_dotenv(dotenv_path)

# Automatically create tables if database is connected
try:
    Base.metadata.create_all(bind=engine)
    print("Database tables initialized successfully.")
except Exception as e:
    print(f"Notice: Database table auto-creation skipped or failed ({e}). Run migrations using Alembic.")

app = FastAPI(
    title="IntelliBusiness API",
    description="Backend API for IntelliBusiness AI-Powered SaaS Platform",
    version="1.0.0"
)

# CORS configuration
cors_origins_str = os.getenv("CORS_ORIGINS", "http://127.0.0.1:3000,http://localhost:3000")
origins = [origin.strip() for origin in cors_origins_str.split(",") if origin.strip()]
if not origins:
    origins = ["http://127.0.0.1:3000", "http://localhost:3000"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include Routers
app.include_router(auth.router)
app.include_router(dashboard.router)
app.include_router(documents.router)


@app.get("/", tags=["Health"])
def read_root():
    return {
        "status": "online",
        "app": "IntelliBusiness API",
        "version": "1.0.0",
        "docs_url": "/docs"
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.app.main:app", host="127.0.0.1", port=8000, reload=True)
