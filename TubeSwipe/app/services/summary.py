import logging
import re
from youtube_transcript_api import YouTubeTranscriptApi
from openai import OpenAI
import google.generativeai as genai
from ..config import settings
from .youtube import get_video_details

logger = logging.getLogger(__name__)

def get_video_summary(video_id: str, youtube_client=None) -> str:
    """Fetches transcript and generates a summary using Gemini (Free) or OpenAI."""
    if not settings.GEMINI_API_KEY and not settings.OPENAI_API_KEY:
        return "Error: No API Key set. Please set GEMINI_API_KEY (Free) or OPENAI_API_KEY in .env"

    full_text = None
    source_note = ""
    
    # Fetch Video Details (Title, Channel, Description)
    video_title = "Unknown Title"
    channel_name = "Unknown Channel"
    video_description = ""
    
    if youtube_client:
        details = get_video_details(youtube_client, video_id)
        if details:
            video_title = details.get('title', 'Unknown Title')
            channel_name = details.get('channelTitle', 'Unknown Channel')
            video_description = details.get('description', '')

    # 1. Try to get Transcript
    try:
        # Try to fetch transcript directly
        try:
            transcript_list = YouTubeTranscriptApi.get_transcript(video_id)
        except Exception:
            # Fallback strategies
            if hasattr(YouTubeTranscriptApi, 'list_transcripts'):
                transcripts = YouTubeTranscriptApi.list_transcripts(video_id)
                try:
                    transcript = transcripts.find_transcript(['en', 'en-US', 'en-GB'])
                except:
                    transcript = next(iter(transcripts))
                transcript_list = transcript.fetch()
            else:
                raise Exception("list_transcripts not supported in this version")
            
        full_text = " ".join([t['text'] for t in transcript_list])
        
    except Exception as e:
        logger.warning(f"Transcript fetch failed: {e}")
        
        # 2. Fallback: Use Video Description
        if video_description:
            logger.info("Falling back to video description...")
            full_text = video_description
            source_note = "\n\n(Summary based on video description as captions were unavailable)"
        else:
             return "No transcript available and could not fetch description."

    if not full_text:
        return "No content available to summarize."

    # Truncate if too long
    if len(full_text) > 10000:
        full_text = full_text[:10000] + "..."

    # Construct Prompt
    system_instruction = (
        "You are an expert video curator. Your task is to provide a concise summary of the video's subject matter. "
        "CRITICAL INSTRUCTIONS:\n"
        "1. **IGNORE** all promotional content, links, merchandise, social media handles, and requests to subscribe.\n"
        "2. **USE EXTERNAL KNOWLEDGE**: If the Title/Channel mentions a person or event (e.g., 'Gabriel', 'Arsenal'), explain who they are and the context, even if the description doesn't.\n"
        "3. **BE DIRECT**: State the facts. Do not say 'The video discusses...'. Just say what happened.\n"
        "4. **FORMAT**: Return the result as a clean HTML unordered list (<ul>) with <li> items. Do NOT use markdown or code blocks.\n"
        "Keep it under 100 words."
    )
    
    prompt_text = (
        f"Video Title: {video_title}\n"
        f"Channel Name: {channel_name}\n\n"
        f"Content to Summarize:\n{full_text}\n\n"
        f"Instructions:\n"
        f"Summarize the actual news or event in an HTML list. Ignore all promotional fluff."
    )

    try:
        # 3. Call LLM
        response_text = ""
        if settings.GEMINI_API_KEY:
            try:
                genai.configure(api_key=settings.GEMINI_API_KEY)
                model = genai.GenerativeModel('gemini-2.0-flash') 
                final_prompt = f"{system_instruction}\n\n{prompt_text}"
                response = model.generate_content(final_prompt)
                response_text = response.text
            except Exception as e:
                logger.error(f"Gemini Error: {e}")
                if not settings.OPENAI_API_KEY:
                    return f"Gemini Error: {str(e)}"
        
        if not response_text and settings.OPENAI_API_KEY:
            client = OpenAI(api_key=settings.OPENAI_API_KEY)
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": system_instruction},
                    {"role": "user", "content": prompt_text}
                ]
            )
            response_text = response.choices[0].message.content
            
        # Strip markdown code blocks if present
        if response_text:
            # Remove ```html ... ``` or just ``` ... ```
            response_text = re.sub(r'^```html\s*', '', response_text, flags=re.IGNORECASE)
            response_text = re.sub(r'^```\s*', '', response_text)
            response_text = re.sub(r'\s*```$', '', response_text)
            return response_text.strip() + source_note
            
        return "Error: Could not generate summary."

    except Exception as e:
        return f"Error generating summary: {str(e)}"
