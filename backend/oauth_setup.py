from pathlib import Path

from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = [
    "https://www.googleapis.com/auth/gmail.send"
]

credentials_file = Path(__file__).with_name("credentials.json")
if not credentials_file.exists():
    alternate_credentials_file = Path(__file__).with_name("credentials.json.json")
    if alternate_credentials_file.exists():
        credentials_file = alternate_credentials_file

flow = InstalledAppFlow.from_client_secrets_file(
    str(credentials_file),
    SCOPES
)

credentials = flow.run_local_server(
    port=8000,
    access_type="offline",
    prompt="consent"
)

print("\nGoogle Gmail authorization completed. Token values were not printed.")
