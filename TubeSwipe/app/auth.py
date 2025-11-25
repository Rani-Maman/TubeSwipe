from google_auth_oauthlib.flow import Flow
from .config import settings
import os

# Allow HTTP for local testing
os.environ["OAUTHLIB_INSECURE_TRANSPORT"] = "1"

def create_flow():
    # In a real app, you would load client_secrets.json or construct from env vars
    # Here we assume env vars are mapped to a client config dict
    client_config = {
        "web": {
            "client_id": settings.GOOGLE_CLIENT_ID,
            "client_secret": settings.GOOGLE_CLIENT_SECRET,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
        }
    }
    
    flow = Flow.from_client_config(
        client_config,
        scopes=settings.SCOPES
    )
    # Force the redirect_uri to be exactly what is in the console
    flow.redirect_uri = settings.REDIRECT_URI
    return flow
