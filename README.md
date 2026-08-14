# IntelliBusiness

IntelliBusiness is a business SaaS platform with a FastAPI backend and a legacy HTML/CSS/JavaScript frontend. The project currently uses a single active frontend implementation under `frontend/`, with the backend and authentication flow preserved from the original app structure.

---

## Project status

This codebase currently includes:
- An active legacy frontend under `frontend/`
- A Python FastAPI backend under `backend/`
- MySQL-ready environment settings via `.env`
- JWT-based login and dashboard authentication flow

The frontend is the original implementation, not a React migration. The project is intentionally kept simple and non-duplicated.

---

## Project structure

```text
IntelliBusiness/
├── backend/
│   ├── alembic/
│   ├── alembic.ini
│   ├── app/
│   │   ├── auth.py
│   │   ├── database.py
│   │   ├── main.py
│   │   ├── models.py
│   │   ├── schemas.py
│   │   ├── security.py
│   │   ├── routers/
│   │   │   ├── auth.py
│   │   │   └── dashboard.py
│   │   └── utils/
│   └── requirements.txt
├── frontend/
│   ├── index.html
│   ├── login.html
│   ├── register.html
│   ├── forgot-password.html
│   ├── dashboard.html
│   ├── css/
│   ├── js/
│   └── assets/
├── uploads/
├── .env
├── .env.example
├── README.md
├── intellibusiness.db
└── requirements.txt
```

---

## Tech stack

### Frontend
- HTML5
- CSS3
- Bootstrap 5
- Vanilla JavaScript
- Static page-based UI

### Backend
- Python
- FastAPI
- SQLAlchemy
- JWT / PyJWT
- MySQL via `pymysql`

---

## Environment configuration

Create or edit the root `.env` file with values like:

```env
DATABASE_URL=mysql+pymysql://root:@localhost:3306/intellibusiness
SECRET_KEY=replace_this_with_a_strong_secret_key
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=1440
CORS_ORIGINS=http://localhost:5173,http://127.0.0.1:5173
```

Important:
- Do not hard-code credentials directly in the source files.
- Use the local MySQL database name `intellibusiness`.
- Keep the frontend running as a static site and the API on port `8000`.

---

## Backend setup

1. Open a terminal in the project root.
2. Create and activate a virtual environment if needed.
3. Install backend dependencies:

```bash
pip install -r backend/requirements.txt
```

4. Start the API:

```bash
uvicorn backend.app.main:app --reload --host 127.0.0.1 --port 8000
```

5. Verify the API is running at:

```text
http://127.0.0.1:8000/docs
```

---

## Frontend setup

Open the frontend directly in the browser, or serve it locally:

```bash
cd frontend
python -m http.server 3000
```

Then visit:

```text
http://localhost:3000
```

---

## Authentication flow

The original app is designed around a simple JWT workflow:
- User registers or logs in from the HTML pages
- Token is stored in browser storage
- Authenticated dashboard pages check for the token
- The backend returns the profile and dashboard data for logged-in users only

---

## Notes

This project is intentionally using the original legacy frontend and not a separate React app. The app is kept simple and stable while the backend remains FastAPI + MySQL backed.

If you want to continue working on it, the most direct path is to modify the existing static frontend pages and keep the backend APIs consistent with them.
