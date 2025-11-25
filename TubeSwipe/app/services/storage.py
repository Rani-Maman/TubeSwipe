import json
import os
import logging

# Use absolute path to ensure we always find the file
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__))) # app/
PROJECT_ROOT = os.path.dirname(BASE_DIR) # project root
MUTED_CHANNELS_FILE = os.path.join(PROJECT_ROOT, 'muted_channels.json')

logger = logging.getLogger(__name__)

def load_muted_channels_dict() -> dict:
    """Loads the dictionary of muted channels {id: name}."""
    if not os.path.exists(MUTED_CHANNELS_FILE):
        return {}
    try:
        with open(MUTED_CHANNELS_FILE, 'r') as f:
            content = f.read().strip()
            if not content:
                return {}
            data = json.loads(content)
            # Backward compatibility: if it's a list, convert to dict with unknown names
            if isinstance(data, list):
                return {cid: "Unknown Channel" for cid in data}
            return data
    except json.JSONDecodeError:
        logger.warning(f"Corrupted muted channels file found at {MUTED_CHANNELS_FILE}. Returning empty dict.")
        return {}
    except Exception as e:
        logger.error(f"Error loading muted channels: {e}")
        return {}

def load_muted_channels() -> set:
    """Loads the set of muted channel IDs (for filtering)."""
    return set(load_muted_channels_dict().keys())

def mute_channel(channel_id: str, channel_title: str = "Unknown Channel") -> bool:
    """Adds a channel ID and title to the muted list."""
    muted = load_muted_channels_dict()
    muted[channel_id] = channel_title
    try:
        with open(MUTED_CHANNELS_FILE, 'w') as f:
            json.dump(muted, f, indent=2)
        return True
    except Exception as e:
        logger.error(f"Error saving muted channels: {e}")
        return False

def unmute_channel(channel_id: str) -> bool:
    """Removes a channel from the muted list."""
    muted = load_muted_channels_dict()
    if channel_id in muted:
        del muted[channel_id]
        try:
            with open(MUTED_CHANNELS_FILE, 'w') as f:
                json.dump(muted, f, indent=2)
            return True
        except Exception as e:
            logger.error(f"Error saving muted channels: {e}")
            return False
    return True
