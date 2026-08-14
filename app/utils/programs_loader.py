import json
import logging
import os
from typing import Dict, List
from app.utils.cache import cache
from app.utils.cache_keys import CacheKeys, CacheTTL

logger = logging.getLogger(__name__)


def _get_programs_file_path() -> str:
    """Get the path to programs.json file."""
    # Look in project root
    project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    return os.path.join(project_root, 'programs.json')


def _load_programs() -> Dict:
    """Load programs from JSON file with caching."""
    cached_data = cache.get(CacheKeys.programs_file())
    if cached_data:
        return cached_data

    file_path = _get_programs_file_path()

    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            cache.set(CacheKeys.programs_file(), data, ttl=CacheTTL.PROGRAMS_FILE)
            logger.debug("✅ [ProgramsLoader] Loaded %d shows from programs.json", len(data.get('shows', [])))
            return data
    except FileNotFoundError:
        logger.warning("⚠️ [ProgramsLoader] programs.json not found at %s", file_path)
        return {"version": "1.0", "shows": []}
    except json.JSONDecodeError as e:
        logger.error("❌ [ProgramsLoader] Error parsing programs.json: %s", e)
        return {"version": "1.0", "shows": []}
    except Exception as e:
        logger.error("❌ [ProgramsLoader] Error loading programs.json: %s", e)
        return {"version": "1.0", "shows": []}


def get_programs_for_provider(provider_name: str) -> Dict[str, Dict]:
    """
    Get all enabled programs for a specific provider.
    
    Args:
        provider_name: Provider identifier (e.g., "6play", "mytf1", "francetv", "cbc")
    
    Returns:
        Dictionary mapping slug to program data
    """
    data = _load_programs()
    shows = data.get('shows', [])
    
    result = {}
    for show in shows:
        if show.get('provider') == provider_name and show.get('enabled', True):
            slug = show.get('slug')
            if slug:
                # Pass every pinned field through untouched. Absent fields stay
                # absent so providers can tell "not set" from "set to empty" and
                # fill them from their metadata API; defaults are applied later
                # by show_meta.build_show_dict.
                program_data = {k: v for k, v in show.items()
                                if k not in ('provider', 'enabled')}
                program_data['id'] = slug
                result[slug] = program_data
    
    logger.debug("✅ [ProgramsLoader] Found %d shows for provider '%s'", len(result), provider_name)
    return result


def get_all_programs() -> List[Dict]:
    """
    Get all enabled programs from all providers.
    
    Returns:
        List of all program configurations
    """
    data = _load_programs()
    shows = data.get('shows', [])
    return [show for show in shows if show.get('enabled', True)]


def reload_programs() -> None:
    """Force reload of programs.json (clears cache)."""
    cache.delete(CacheKeys.programs_file())
    logger.info("🔄 [ProgramsLoader] Programs cache cleared")
