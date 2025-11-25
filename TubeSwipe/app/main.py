from fastapi import FastAPI, Request, Depends, HTTPException
from fastapi.responses import RedirectResponse, HTMLResponse
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware
from pydantic import BaseModel
from app.config import settings
from app.models import SwipeAction

from google.auth.exceptions import RefreshError
from app.services.youtube import (
    get_youtube_client, 
    get_feed, 
    get_or_create_playlist, 
    add_video_to_playlist,
    get_user_playlists,
    create_playlist
)
from app.services.summary import get_video_summary
from app.services.storage import mute_channel, unmute_channel, load_muted_channels_dict
from app.auth import create_flow

app = FastAPI()

# Add session middleware for simple token storage
app.add_middleware(SessionMiddleware, secret_key=settings.SECRET_KEY)

templates = Jinja2Templates(directory="templates")

class MuteRequest(BaseModel):
    channel_id: str
    channel_title: str

class UnmuteRequest(BaseModel):
    channel_id: str

class CreatePlaylistRequest(BaseModel):
    title: str
    description: str = "Created via TubeSwipe"
    privacy: str = "private"

@app.get("/favicon.ico", include_in_schema=False)
async def favicon():
    return HTMLResponse("")

@app.get("/")
def home(request: Request):
    # Check if logged in
    if "credentials" not in request.session:
        return templates.TemplateResponse(request=request, name="index.html", context={"logged_in": False})
    return templates.TemplateResponse(request=request, name="index.html", context={"logged_in": True})

@app.get("/login")
def login(request: Request):
    if settings.MOCK_MODE:
        return RedirectResponse("/auth/callback?mock=true")

    flow = create_flow()
    authorization_url, state = flow.authorization_url(
        access_type='offline',
        include_granted_scopes='true',
        prompt='consent'
    )
    request.session["state"] = state
    return RedirectResponse(authorization_url)

@app.get("/auth/callback")
def auth_callback(request: Request):
    if request.query_params.get("mock"):
        request.session["credentials"] = {
            "mock": True,
            "token": "mock_token",
            "refresh_token": "mock_refresh",
            "scopes": []
        }
        return RedirectResponse("/")

    state = request.session.get("state")
    if not state:
        raise HTTPException(status_code=400, detail="State missing")
        
    flow = create_flow()
    # IMPORTANT: The redirect_uri here must match exactly what was used in the authorization step
    flow.redirect_uri = settings.REDIRECT_URI
    
    # Use the full URL from the request to fetch the token
    # We need to ensure it starts with https if running behind a proxy, but for localhost http is fine
    authorization_response = str(request.url)
    
    # Fix for http vs https mismatch on some setups
    if authorization_response.startswith('http:') and settings.REDIRECT_URI.startswith('https:'):
        authorization_response = authorization_response.replace('http:', 'https:', 1)
        
    flow.fetch_token(authorization_response=authorization_response)
    
    creds = flow.credentials
    
    # Store credentials in session (In prod, store in DB and use session ID)
    request.session["credentials"] = {
        "token": creds.token,
        "refresh_token": creds.refresh_token,
        "token_uri": creds.token_uri,
        "client_id": creds.client_id,
        "client_secret": creds.client_secret,
        "scopes": creds.scopes
    }
    
    return RedirectResponse("/")

@app.get("/api/feed")
async def get_video_feed(request: Request, include_shorts: bool = True, playlist_id: str = None, refresh: bool = False):
    if "credentials" not in request.session:
        raise HTTPException(status_code=401, detail="Not authenticated")
        
    creds_dict = request.session["credentials"]
    
    if creds_dict.get("mock"):
        token_info = {"mock": True}
    else:
        # Reconstruct credentials dict for our service helper
        # Note: The dict structure in session matches what Credentials expects mostly, 
        # but we need to map it correctly in services.py
        
        # We need to pass the client_id/secret again because they might not be in the creds object directly 
        # depending on how it was created, but we stored them.
        token_info = {
            'access_token': creds_dict['token'],
            'refresh_token': creds_dict['refresh_token'],
            'client_id': settings.GOOGLE_CLIENT_ID,
            'client_secret': settings.GOOGLE_CLIENT_SECRET,
            'scopes': creds_dict['scopes']
        }
    
    try:
        youtube = get_youtube_client(token_info)
        # Handle empty string playlist_id
        if not playlist_id:
            playlist_id = None
            
        videos = await get_feed(youtube, include_shorts=include_shorts, check_playlist_id=playlist_id, force_refresh=refresh)
        return videos
    except RefreshError:
        # Token expired and refresh failed (likely missing refresh_token)
        request.session.clear() # Clear the invalid session
        raise HTTPException(status_code=401, detail="Session expired, please login again")
    except Exception as e:
        # Log the full error for debugging
        print(f"Error fetching feed: {e}")
        # Return a more user-friendly error
        raise HTTPException(status_code=500, detail="An error occurred while fetching the video feed.")

@app.post("/api/swipe")
def swipe_video(action: SwipeAction, request: Request):
    if "credentials" not in request.session:
        raise HTTPException(status_code=401, detail="Not authenticated")
        
    if action.action == "skip":
        return {"status": "skipped"}
        
    if action.action == "save":
        creds_dict = request.session["credentials"]
        if creds_dict.get("mock"):
            token_info = {"mock": True}
        else:
            token_info = {
                'access_token': creds_dict['token'],
                'refresh_token': creds_dict['refresh_token'],
                'client_id': settings.GOOGLE_CLIENT_ID,
                'client_secret': settings.GOOGLE_CLIENT_SECRET,
                'scopes': creds_dict['scopes']
            }
        youtube = get_youtube_client(token_info)
        
        if action.playlist_id:
            playlist_id = action.playlist_id
        else:
            playlist_id = get_or_create_playlist(youtube)
            
        success = add_video_to_playlist(youtube, playlist_id, action.video_id)
        
        if success:
            return {"status": "saved"}
        else:
            return {"status": "error", "message": "Could not save video"}
            
    return {"status": "invalid_action"}

@app.get("/api/summary/{video_id}")
def get_summary(video_id: str, request: Request):
    if "credentials" not in request.session:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    creds_dict = request.session["credentials"]
    
    if creds_dict.get("mock"):
        token_info = {"mock": True}
    else:
        token_info = {
            'access_token': creds_dict['token'],
            'refresh_token': creds_dict['refresh_token'],
            'client_id': settings.GOOGLE_CLIENT_ID,
            'client_secret': settings.GOOGLE_CLIENT_SECRET,
            'scopes': creds_dict['scopes']
        }
    
    youtube = get_youtube_client(token_info)
    summary = get_video_summary(video_id, youtube_client=youtube)
    return {"summary": summary}

@app.post("/api/mute")
def mute_channel_endpoint(data: MuteRequest, request: Request):
    if "credentials" not in request.session:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    success = mute_channel(data.channel_id, data.channel_title)
    if success:
        return {"status": "muted", "channel": data.channel_title}
    else:
        raise HTTPException(status_code=500, detail="Could not mute channel")

@app.post("/api/unmute")
def unmute_channel_endpoint(data: UnmuteRequest, request: Request):
    if "credentials" not in request.session:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    success = unmute_channel(data.channel_id)
    if success:
        return {"status": "unmuted"}
    else:
        raise HTTPException(status_code=500, detail="Could not unmute channel")

@app.get("/api/muted-channels")
def get_muted_channels(request: Request):
    if "credentials" not in request.session:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    muted = load_muted_channels_dict()
    # Return as list of objects for easier frontend consumption
    return [{"id": k, "name": v} for k, v in muted.items()]

@app.get("/api/playlists")
def list_playlists(request: Request):
    if "credentials" not in request.session:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    creds_dict = request.session["credentials"]
    
    if creds_dict.get("mock"):
        token_info = {"mock": True}
    else:
        token_info = {
            'access_token': creds_dict['token'],
            'refresh_token': creds_dict['refresh_token'],
            'client_id': settings.GOOGLE_CLIENT_ID,
            'client_secret': settings.GOOGLE_CLIENT_SECRET,
            'scopes': creds_dict['scopes']
        }
        
    youtube = get_youtube_client(token_info)
    playlists = get_user_playlists(youtube)
    return playlists

@app.post("/api/playlists")
def create_new_playlist(data: CreatePlaylistRequest, request: Request):
    if "credentials" not in request.session:
        raise HTTPException(status_code=401, detail="Not authenticated")
        
    creds_dict = request.session["credentials"]
    
    if creds_dict.get("mock"):
        token_info = {"mock": True}
    else:
        token_info = {
            'access_token': creds_dict['token'],
            'refresh_token': creds_dict['refresh_token'],
            'client_id': settings.GOOGLE_CLIENT_ID,
            'client_secret': settings.GOOGLE_CLIENT_SECRET,
            'scopes': creds_dict['scopes']
        }
        
    youtube = get_youtube_client(token_info)
    result = create_playlist(youtube, data.title, data.privacy, data.description)
    if result:
        return result
    raise HTTPException(status_code=500, detail="Failed to create playlist")

@app.get("/logout")
def logout(request: Request):
    request.session.clear()
    return RedirectResponse("/")
