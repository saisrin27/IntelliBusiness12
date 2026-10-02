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
CORS_ORIGINS=http://127.0.0.1:3000,http://localhost:3000,https://intelli-business12.vercel.app
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
uvicorn backend.app.main:app --reload --no-access-log --host 127.0.0.1 --port 8000
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

## Production deployment

### Render backend

Use the repository root as the Render service root. Set the build command to:

```bash
pip install -r backend/requirements.txt
```

Set the start command to:

```bash
uvicorn backend.app.main:app --no-access-log --host 0.0.0.0 --port $PORT
```

Run `python -m alembic -c backend/alembic.ini upgrade head` as the deployment pre-deploy/release command after configuring `DATABASE_URL`. Configure `SECRET_KEY`, `DATABASE_URL`, `CORS_ORIGINS`, `FRONTEND_BASE_URL`, `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `GMAIL_REFRESH_TOKEN`, `GEMINI_API_KEY`, and `AI_API_KEY` as Render environment variables. Never put these values in the repository. App email is always sent from `intellibusiness12@gmail.com`; the sender address is fixed in the backend.

### Central Gmail authorization (one-time admin setup)

Google Sign-In for IntelliBusiness users is separate from Gmail sending. Only an administrator authorizes the central sender account; normal users do not connect Gmail.

1. In the Google Cloud project used by the OAuth client, enable the **Gmail API** and configure the OAuth consent screen.
2. The existing `backend/credentials.json` is a **Web application** OAuth client. In Google Cloud Console, add `http://localhost:8765/` as an authorized redirect URI for that client. This is only for the local admin authorization helper and does not change the Google Sign-In callback.
3. From the repository root, run `python backend/oauth_setup.py`. Sign into `intellibusiness12@gmail.com` in the browser and grant the requested Gmail send permission. The helper verifies the account and saves only the refresh token to the ignored file `backend/gmail_refresh_token.txt`; it never prints the token.
4. For local sending, set `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, and `GMAIL_REFRESH_TOKEN` in the root `.env`. The OAuth client ID and secret must belong to the same Google Cloud OAuth client used to create the refresh token. Copy the refresh token from the ignored local file directly into the `.env` value; never commit or paste it into source code.
5. Start the backend and frontend using the local setup above, then send a test email to an address you control. The backend logs whether the client configuration and refresh token are present, which Google account authorized sending, whether the Gmail API client initialized, and sanitized Google API error reasons. It never logs OAuth secrets or tokens.
6. In Render's backend service, add `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, and `GMAIL_REFRESH_TOKEN` as private environment variables. Transfer the refresh token directly from the local ignored file into Render's environment-variable form; do not put it in Git, frontend settings, logs, or chat. Save the variables and redeploy, then test a send and inspect the Render logs for the Gmail diagnostics.

If the OAuth consent screen remains in **Testing** for an external app, Google may expire refresh tokens after seven days. Publish/configure the consent screen as appropriate for the deployment, then repeat the one-time authorization if the logs report an invalid or revoked refresh token.

### Vercel frontend

Set the Vercel project root directory to `frontend/` and deploy as a static site without a build command. The browser client selects localhost for local pages and the Render API for the deployed Vercel hostname; no secret or backend credential belongs in Vercel frontend code.

Register this exact production Google redirect URI in Google Cloud Console:

```text
https://intellibusiness-db.onrender.com/api/auth/google/callback
```

For local development, set `GOOGLE_REDIRECT_URI=http://127.0.0.1:8000/api/auth/google/callback` and `FRONTEND_BASE_URL=http://127.0.0.1:3000`. The local redirect URI must also be registered in Google Cloud Console.

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
