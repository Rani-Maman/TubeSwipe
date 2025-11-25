import re
import asyncio
import httpx

def parse_duration(duration: str) -> int:
    """Parses YouTube duration string (e.g., PT1H2M10S) to seconds."""
    if not duration:
        return 0
    match = re.match(r'PT(\d+H)?(\d+M)?(\d+S)?', duration)
    if not match:
        return 0
    
    hours = int(match.group(1)[:-1]) if match.group(1) else 0
    minutes = int(match.group(2)[:-1]) if match.group(2) else 0
    seconds = int(match.group(3)[:-1]) if match.group(3) else 0
    
    return hours * 3600 + minutes * 60 + seconds

async def check_is_short_parallel(video_ids):
    """
    Checks if videos are Shorts by making parallel HEAD requests to youtube.com/shorts/{video_id}.
    Returns a set of video_ids that are confirmed Shorts.
    """
    shorts_set = set()
    
    async def check_single(client, vid):
        try:
            # Follow redirects=False. 
            # If it's a Short, it returns 200 OK.
            # If it's a Video, it returns 303 See Other (redirect to /watch).
            resp = await client.head(f"https://www.youtube.com/shorts/{vid}", follow_redirects=False)
            if resp.status_code == 200:
                return vid
        except Exception:
            pass
        return None

    async with httpx.AsyncClient() as client:
        tasks = [check_single(client, vid) for vid in video_ids]
        results = await asyncio.gather(*tasks)
        
    for res in results:
        if res:
            shorts_set.add(res)
            
    return shorts_set
