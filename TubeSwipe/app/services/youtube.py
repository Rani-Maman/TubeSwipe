import logging
import time
from datetime import datetime, timedelta, timezone
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials
from .utils import parse_duration, check_is_short_parallel
from .storage import load_muted_channels
from ..config import settings

logger = logging.getLogger(__name__)

# Simple In-Memory Cache
FEED_CACHE = {
    "data": None,
    "timestamp": 0
}
CACHE_DURATION = 300  # 5 minutes in seconds

def get_youtube_client(token_info: dict):
    # If we are in mock mode (passed via token_info or detected otherwise), return None
    if token_info.get('mock'):
        return None

    creds = Credentials(
        token=token_info['access_token'],
        refresh_token=token_info.get('refresh_token'),
        token_uri="https://oauth2.googleapis.com/token",
        client_id=token_info['client_id'],
        client_secret=token_info['client_secret'],
        scopes=token_info['scopes']
    )
    return build('youtube', 'v3', credentials=creds)

def get_mock_feed():
    """Returns fake video data for testing without API keys."""
    return [
        {
            "video_id": "dQw4w9WgXcQ",
            "title": "Rick Astley - Never Gonna Give You Up (Official Music Video)",
            "channel_title": "Rick Astley",
            "thumbnail_url": "https://i.ytimg.com/vi/dQw4w9WgXcQ/hqdefault.jpg",
            "published_at": "2009-10-25T10:00:00Z",
            "channel_id": "UCuAXFkgsw1L7xaCfnd5JJOw"
        },
        {
            "video_id": "jNQXAC9IVRw",
            "title": "Me at the zoo",
            "channel_title": "jawed",
            "thumbnail_url": "https://i.ytimg.com/vi/jNQXAC9IVRw/hqdefault.jpg",
            "published_at": "2005-04-24T03:31:52Z",
            "channel_id": "UC4QZ_LsYcvcqPqGSqIZShGA"
        },
        {
            "video_id": "9bZkp7q19f0",
            "title": "PSY - GANGNAM STYLE(강남스타일) M/V",
            "channel_title": "officialpsy",
            "thumbnail_url": "https://i.ytimg.com/vi/9bZkp7q19f0/hqdefault.jpg",
            "published_at": "2012-07-15T07:46:32Z",
            "channel_id": "UCrDkAvwZum-UTjHmzDI2iIw"
        }
    ]

def get_subscriptions(youtube):
    """Fetch user's subscriptions (first 50)."""
    request = youtube.subscriptions().list(
        part="snippet,contentDetails",
        mine=True,
        maxResults=50
    )
    response = request.execute()
    return response.get("items", [])

def get_uploads_playlist_ids(youtube, channel_ids):
    """Get the uploads playlist ID for a list of channels."""
    # API allows batching up to 50 ids
    ids_string = ",".join(channel_ids)
    request = youtube.channels().list(
        part="contentDetails",
        id=ids_string
    )
    response = request.execute()
    
    playlist_ids = []
    for item in response.get("items", []):
        uploads_id = item["contentDetails"]["relatedPlaylists"]["uploads"]
        playlist_ids.append(uploads_id)
    return playlist_ids

def get_recent_videos_from_playlists(youtube, playlist_ids):
    """Fetch the most recent video from each playlist."""
    videos = []
    # Note: This is expensive on quota (1 unit per call). 
    # 50 subs = 50 calls = 50 units.
    # In production, you would cache this or use a worker.
    
    for pid in playlist_ids:
        try:
            request = youtube.playlistItems().list(
                part="snippet,contentDetails",
                playlistId=pid,
                maxResults=5  # Fetch last 5 videos
            )
            response = request.execute()
            items = response.get("items", [])
            if items:
                videos.extend(items)
        except Exception as e:
            logger.error(f"Error fetching playlist {pid}: {e}")
            continue
            
    return videos

def get_playlist_video_ids(youtube, playlist_id):
    """Fetches video IDs from the playlist."""
    if youtube is None:
        return set()
        
    video_ids = set()
    next_page_token = None
    
    # Limit to first 500 (10 pages) to catch more videos
    # This is a trade-off between performance and accuracy
    for _ in range(10): 
        try:
            request = youtube.playlistItems().list(
                part="contentDetails",
                playlistId=playlist_id,
                maxResults=50,
                pageToken=next_page_token
            )
            response = request.execute()
            
            for item in response.get("items", []):
                video_ids.add(item["contentDetails"]["videoId"])
                
            next_page_token = response.get("nextPageToken")
            if not next_page_token:
                break
        except Exception as e:
            logger.error(f"Error fetching playlist items: {e}")
            break
            
    return video_ids

def get_video_durations(youtube, video_ids):
    """Fetches durations for a list of video IDs."""
    durations = {}
    # Batch in 50s
    for i in range(0, len(video_ids), 50):
        batch = video_ids[i:i+50]
        try:
            request = youtube.videos().list(
                part="contentDetails",
                id=",".join(batch)
            )
            response = request.execute()
            for item in response.get("items", []):
                durations[item["id"]] = parse_duration(item["contentDetails"]["duration"])
        except Exception as e:
            logger.error(f"Error fetching durations: {e}")
    return durations

def get_video_details(youtube, video_id):
    """Fetches video title and description using the official API."""
    if youtube is None:
        return None
    try:
        request = youtube.videos().list(
            part="snippet",
            id=video_id
        )
        response = request.execute()
        if response["items"]:
            return response["items"][0]["snippet"]
    except Exception as e:
        logger.error(f"Error fetching video details: {e}")
    return None

def get_or_create_playlist(youtube, title="TubeSwipe Saved"):
    """Finds a playlist by title or creates it."""
    if youtube is None:
        logger.info(f"MOCK: Created/Found playlist '{title}'")
        return "mock_playlist_id"

    # 1. List user's playlists
    request = youtube.playlists().list(
        part="snippet",
        mine=True,
        maxResults=50
    )
    response = request.execute()
    
    for item in response.get("items", []):
        if item["snippet"]["title"] == title:
            return item["id"]
            
    # 2. Create if not found
    request = youtube.playlists().insert(
        part="snippet,status",
        body={
            "snippet": {
                "title": title,
                "description": "Videos saved from TubeSwipe App"
            },
            "status": {
                "privacyStatus": "private" 
            }
        }
    )
    response = request.execute()
    return response["id"]

def add_video_to_playlist(youtube, playlist_id, video_id):
    """Adds a video to the specified playlist."""
    if youtube is None:
        logger.info(f"MOCK: Added video {video_id} to playlist {playlist_id}")
        return True

    try:
        request = youtube.playlistItems().insert(
            part="snippet",
            body={
                "snippet": {
                    "playlistId": playlist_id,
                    "resourceId": {
                        "kind": "youtube#video",
                        "videoId": video_id
                    }
                }
            }
        )
        request.execute()
        return True
    except Exception as e:
        # Video might already be in playlist
        logger.error(f"Error adding video: {e}")
        return False

def get_user_playlists(youtube):
    """Fetches all playlists for the authenticated user."""
    if youtube is None:
        return [{"id": "mock_playlist_id", "title": "Mock Playlist", "thumbnail": "", "privacy": "private"}]
    
    playlists = []
    
    # 2. Fetch Created Playlists
    next_page_token = None
    
    while True:
        try:
            request = youtube.playlists().list(
                part="snippet,status",
                mine=True,
                maxResults=50,
                pageToken=next_page_token
            )
            response = request.execute()
            
            for item in response.get("items", []):
                thumbnails = item["snippet"].get("thumbnails", {})
                default_thumb = thumbnails.get("default", {}).get("url", "")
                
                playlists.append({
                    "id": item["id"],
                    "title": item["snippet"]["title"],
                    "thumbnail": default_thumb,
                    "privacy": item.get("status", {}).get("privacyStatus", "unknown")
                })
                
            next_page_token = response.get("nextPageToken")
            if not next_page_token:
                break
        except Exception as e:
            logger.error(f"Error fetching playlists: {e}")
            break
            
    return playlists

def create_playlist(youtube, title, privacy_status="private", description="Created via TubeSwipe"):
    """Creates a new playlist."""
    if youtube is None:
        return {"id": "mock_new_id", "title": title, "privacy": privacy_status}
        
    try:
        request = youtube.playlists().insert(
            part="snippet,status",
            body={
                "snippet": {
                    "title": title,
                    "description": description
                },
                "status": {
                    "privacyStatus": privacy_status 
                }
            }
        )
        response = request.execute()
        return {
            "id": response["id"],
            "title": response["snippet"]["title"],
            "privacy": response["status"]["privacyStatus"]
        }
    except Exception as e:
        logger.error(f"Error creating playlist: {e}")
        return None

async def get_feed(youtube, include_shorts=True, check_playlist_id=None, force_refresh=False):
    """Orchestrate the feed generation with caching."""
    global FEED_CACHE
    
    # Check Cache (only if not forcing refresh and no specific playlist filter)
    cache_key = f"shorts:{include_shorts}"
    
    print(f"[CACHE DEBUG] Request: key={cache_key}, force_refresh={force_refresh}, playlist_id={check_playlist_id}")
    print(f"[CACHE DEBUG] Cache state: has_data={bool(FEED_CACHE['data'])}, stored_key={FEED_CACHE.get('key')}, age={time.time() - FEED_CACHE['timestamp']:.1f}s")
    
    if not force_refresh and not check_playlist_id and FEED_CACHE["data"]:
        # Check if key matches (so we don't serve non-shorts feed when shorts requested)
        if FEED_CACHE.get("key") == cache_key:
            current_time = time.time()
            age = current_time - FEED_CACHE["timestamp"]
            if age < CACHE_DURATION:
                print(f"[CACHE DEBUG] ✓ CACHE HIT! Serving {len(FEED_CACHE['data'])} videos from cache")
                logger.info("Serving feed from cache")
                return FEED_CACHE["data"]
            else:
                print(f"[CACHE DEBUG] ✗ Cache expired (age: {age:.1f}s > limit: {CACHE_DURATION}s)")
        else:
            print(f"[CACHE DEBUG] ✗ Cache key mismatch: stored={FEED_CACHE.get('key')} vs requested={cache_key}")
    else:
        print(f"[CACHE DEBUG] ✗ Cache miss reasons: force={force_refresh}, playlist={check_playlist_id}, has_data={bool(FEED_CACHE['data'])}")

    if youtube is None:
        return get_mock_feed()

    # 1. Get Subs
    subs = get_subscriptions(youtube)
    if not subs:
        return []
        
    # 2. Extract Channel IDs
    channel_ids = [item["snippet"]["resourceId"]["channelId"] for item in subs]
    
    # 3. Get Upload Playlist IDs
    upload_playlist_ids = get_uploads_playlist_ids(youtube, channel_ids)
    
    # 4. Get Recent Videos
    raw_videos = get_recent_videos_from_playlists(youtube, upload_playlist_ids)
    


    # Filter Muted Channels
    muted_channels = load_muted_channels()
    raw_videos = [v for v in raw_videos if v["snippet"]["channelId"] not in muted_channels]

    # Filter by Date (Last 48 Hours)
    cutoff_time = datetime.now(timezone.utc) - timedelta(hours=48)
    
    filtered_videos = []
    for v in raw_videos:
        try:
            # publishedAt is like "2023-10-25T10:00:00Z"
            pub_str = v["snippet"]["publishedAt"]
            # Handle Z for UTC
            if pub_str.endswith('Z'):
                pub_str = pub_str[:-1] + '+00:00'
            
            pub_date = datetime.fromisoformat(pub_str)
            
            if pub_date >= cutoff_time:
                filtered_videos.append(v)
        except Exception as e:
            logger.warning(f"Error parsing date for video {v.get('id')}: {e}")
            # Keep it if we can't parse it, or drop it? Let's drop to be safe/clean.
            continue
            
    raw_videos = filtered_videos

    # Filter Shorts if requested
    if not include_shorts and youtube:
        video_ids = [v["snippet"]["resourceId"]["videoId"] for v in raw_videos]
        
        # Parallel Check
        shorts_ids = await check_is_short_parallel(video_ids)
        
        # Filter out confirmed Shorts
        raw_videos = [v for v in raw_videos if v["snippet"]["resourceId"]["videoId"] not in shorts_ids]

    # 5. Sort by Date (newest first)
    raw_videos.sort(
        key=lambda x: x["snippet"]["publishedAt"], 
        reverse=True
    )
    
    # 6. Format & Check Saved Status across ALL playlists
    formatted_videos = []
    saved_video_map = {} # video_id -> list of playlist titles
    
    if youtube:
        try:
            # Fetch all user playlists
            playlists = get_user_playlists(youtube)
            
            # Check each playlist
            for pl in playlists:
                try:
                    p_ids = get_playlist_video_ids(youtube, pl['id'])
                    for vid in p_ids:
                        if vid not in saved_video_map:
                            saved_video_map[vid] = []
                        
                        # Check if this playlist ID is already in the list for this video
                        if not any(p['id'] == pl['id'] for p in saved_video_map[vid]):
                            saved_video_map[vid].append({'id': pl['id'], 'title': pl['title']})
                            
                except Exception as e:
                    logger.warning(f"Could not fetch items for playlist {pl['title']}: {e}")
        except Exception as e:
            logger.error(f"Error fetching user playlists: {e}")

    for video in raw_videos:
        vid_id = video["snippet"]["resourceId"]["videoId"]
        
        # Determine saved status
        is_saved = vid_id in saved_video_map
        saved_to = saved_video_map.get(vid_id, [])
        
        formatted_videos.append({
            "video_id": vid_id,
            "title": video["snippet"]["title"],
            "channel_title": video["snippet"]["channelTitle"],
            "thumbnail_url": video["snippet"]["thumbnails"]["high"]["url"],
            "published_at": video["snippet"]["publishedAt"],
            "channel_id": video["snippet"]["channelId"],
            "saved": is_saved,
            "saved_to": saved_to
        })
        
    # Update Cache (only if not filtering by playlist)
    if not check_playlist_id:
        FEED_CACHE["data"] = formatted_videos
        FEED_CACHE["timestamp"] = time.time()
        FEED_CACHE["key"] = cache_key
        print(f"[CACHE DEBUG] ✓ Cache updated: {len(formatted_videos)} videos, key={cache_key}")
        logger.info(f"Feed cache updated. Items: {len(formatted_videos)}")
    else:
        print(f"[CACHE DEBUG] ✗ Not caching (playlist filter active: {check_playlist_id})")
        
    return formatted_videos
