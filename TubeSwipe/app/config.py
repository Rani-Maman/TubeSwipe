import os
from dotenv import load_dotenv

load_dotenv()

class Settings:
    GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
    GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")
    SECRET_KEY = os.getenv("SECRET_KEY", "random_secret_string_for_session")
    REDIRECT_URI = "http://localhost:8000/auth/callback"
    # Scopes needed: Read subs, read playlists, manage playlists (to create/add)
    SCOPES = [
        "https://www.googleapis.com/auth/youtube.readonly",
        "https://www.googleapis.com/auth/youtube.force-ssl"
    ]
    
    # If keys are missing, default to Mock Mode
    MOCK_MODE = os.getenv("MOCK_MODE", "False").lower() == "true" or not GOOGLE_CLIENT_ID

    # OpenAI Key for summaries
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
    
    # Gemini API Key for free summaries
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

settings = Settings()
