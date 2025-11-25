import asyncio
import httpx
import time

VIDEO_IDS = [
    "dQw4w9WgXcQ", # Rick Roll (Video)
    "jNQXAC9IVRw", # Me at the zoo (Video)
    "9bZkp7q19f0", # Gangnam Style (Video)
    "t433PEQGErc", # Short (Example)
    "5wF_8J139pE", # Short
    "ShortIDHere", # Placeholder
]

# Let's generate a list of 20 dummy IDs to simulate a batch
# We'll use real IDs repeated to ensure valid network responses
TEST_BATCH = ["dQw4w9WgXcQ", "jNQXAC9IVRw", "9bZkp7q19f0"] * 7 # 21 videos

async def check_is_short(client, video_id):
    url = f"https://www.youtube.com/shorts/{video_id}"
    try:
        # Follow redirects=False to see the 303
        resp = await client.head(url, follow_redirects=False)
        # If 200, it's a Short. If 303 (See Other) -> /watch, it's a Video.
        is_short = resp.status_code == 200
        return video_id, is_short, resp.status_code
    except Exception as e:
        return video_id, None, str(e)

async def main():
    print(f"Testing batch of {len(TEST_BATCH)} videos...")
    start_time = time.time()
    
    async with httpx.AsyncClient() as client:
        tasks = [check_is_short(client, vid) for vid in TEST_BATCH]
        results = await asyncio.gather(*tasks)
        
    end_time = time.time()
    duration = end_time - start_time
    
    print(f"Completed in {duration:.2f} seconds.")
    
    shorts_count = 0
    videos_count = 0
    errors = 0
    
    for vid, is_short, status in results:
        if is_short is True:
            shorts_count += 1
        elif is_short is False:
            videos_count += 1
        else:
            errors += 1
            print(f"Error for {vid}: {status}")
            
    print(f"Shorts: {shorts_count}, Videos: {videos_count}, Errors: {errors}")

if __name__ == "__main__":
    asyncio.run(main())
