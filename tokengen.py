from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/drive.file"
]

flow = InstalledAppFlow.from_client_secrets_file(
    "client_secret.json", SCOPES
)

creds = flow.run_local_server(port=0)

print("ACCESS TOKEN:", creds.token)
print("REFRESH TOKEN:", creds.refresh_token)