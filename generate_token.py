from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = [
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/spreadsheets",
]

flow = InstalledAppFlow.from_client_secrets_file("data/credentials.json", SCOPES)
creds = flow.run_local_server(port=0)

with open("data/token.json", "w") as token:
    token.write(creds.to_json())

print("✅ Nuevo data/token.json generado con éxito.")