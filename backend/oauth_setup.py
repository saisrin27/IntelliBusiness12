import json
import os
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2 import id_token
from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = [
    "openid",
    "https://www.googleapis.com/auth/userinfo.email",
    "https://www.googleapis.com/auth/gmail.send",
]
CENTRAL_GMAIL_SENDER = "intellibusiness12@gmail.com"
REDIRECT_URI = "http://localhost:8765/"

backend_dir = Path(__file__).resolve().parent
credentials_file = backend_dir / "credentials.json"
refresh_token_file = backend_dir / "gmail_refresh_token.txt"

if not credentials_file.is_file():
    raise SystemExit("OAuth client file not found: backend/credentials.json")

try:
    client_config = json.loads(credentials_file.read_text(encoding="utf-8"))
    client_id = client_config.get("web", {}).get("client_id") or client_config.get("installed", {}).get("client_id")
except (OSError, ValueError, TypeError):
    raise SystemExit("OAuth client file is invalid. Its contents were not displayed.")

if not client_id:
    raise SystemExit("OAuth client file must contain a web or installed OAuth client.")

flow = InstalledAppFlow.from_client_secrets_file(
    str(credentials_file),
    SCOPES
)
flow.redirect_uri = REDIRECT_URI
credentials = flow.run_local_server(
    host="localhost",
    port=8765,
    access_type="offline",
    prompt="consent select_account",
)

if not credentials.refresh_token:
    raise SystemExit(
        "Google did not return a refresh token. Revoke this app's access for the central account and run the authorization again."
    )

try:
    identity = id_token.verify_oauth2_token(
        credentials.id_token,
        Request(),
        audience=client_id,
    )
except Exception as exc:
    raise SystemExit(f"Could not verify the authorized Google account ({type(exc).__name__}).")

authorized_email = str(identity.get("email", "")).strip().lower()
if authorized_email != CENTRAL_GMAIL_SENDER:
    raise SystemExit(
        f"Wrong Google account authorized: {authorized_email or 'email unavailable'}. "
        f"Sign in as {CENTRAL_GMAIL_SENDER} and run the authorization again. No token was saved."
    )

refresh_token_file.write_text(credentials.refresh_token + "\n", encoding="utf-8")
try:
    os.chmod(refresh_token_file, 0o600)
except OSError:
    pass

print(f"Authorized account: {authorized_email}")
print(f"Refresh token saved locally to {refresh_token_file}")
print("The token value was not printed. Do not commit or share this file.")