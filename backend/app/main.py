import os
import sys
import time
from pathlib import Path
from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
from sqlalchemy import inspect, text
from sqlalchemy.orm import Session

# Ensure root directory and backend directory are in sys.path
current_dir = Path(__file__).resolve().parent
backend_dir = current_dir.parent
root_dir = backend_dir.parent

for p in [str(root_dir), str(backend_dir)]:
    if p not in sys.path:
        sys.path.insert(0, p)

from .database import engine, Base, get_db
from .models import Document, User
from .routers import admin, ai_assistant, analytics, auth, business_analytics, dashboard, documents, emails, settings, workflows

# Load environment variables
dotenv_path = root_dir / ".env"
if os.path.exists(dotenv_path):
    load_dotenv(dotenv_path, override=True)

# Ensure existing installations have the role field and fixed admin role.
def ensure_admin_role():
    try:
        inspector = inspect(engine)
        if "users" in inspector.get_table_names():
            columns = {column["name"] for column in inspector.get_columns("users")}
            if "role" not in columns:
                with engine.begin() as connection:
                    if engine.dialect.name == "mysql":
                        connection.execute(text("ALTER TABLE users ADD COLUMN role VARCHAR(50) NOT NULL DEFAULT 'user'"))
                    else:
                        connection.execute(text("ALTER TABLE users ADD COLUMN role VARCHAR(50) NOT NULL DEFAULT 'user'"))
    except Exception as e:
        print(f"Notice: User role schema repair skipped ({e}).")


ensure_admin_role()

server_started_at = time.monotonic()

# Automatically create tables if database is connected
try:
    Base.metadata.create_all(bind=engine)
    with engine.begin() as connection:
        connection.execute(text(
            "UPDATE users SET role = 'admin' "
            "WHERE LOWER(email) = 'intellibusiness12@gmail.com'"
        ))
        connection.execute(text("UPDATE user_settings SET theme = 'light'"))
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
app.include_router(ai_assistant.router)
app.include_router(emails.router)
app.include_router(workflows.router)
app.include_router(analytics.router)
app.include_router(business_analytics.router)
app.include_router(admin.router)
app.include_router(settings.router)







@app.get("/api/public/stats", tags=["Public"])
def read_public_stats(db: Session = Depends(get_db)):
    return {
        "registered_users": db.query(User).count(),
        "uploaded_documents": db.query(Document).count(),
        "uptime_seconds": int(time.monotonic() - server_started_at),
    }


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
