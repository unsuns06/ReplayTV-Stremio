"""
Programs Loader Utility

Loads TV show configurations from programs.json and provides
filtered access by provider.
"""

import json
import os
from typing import Dict, List, Optional
from app.utils.safe_print import safe_print
from app.utils.cache import cache


def _get_programs_file_path() -> str:
    """Get the path to programs.json file."""
    # Look in project root
    project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    return os.path.join(project_root, 'programs.json')


def _load_programs() -> Dict:
    """Load programs from JSON file with caching."""
    cached_data = cache.get("programs_data")
    if cached_data:
        return cached_data
    
    file_path = _get_programs_file_path()
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            # Cache for 1 hour
            cache.set("programs_data", data, ttl=3600)
            safe_print(f"✅ [ProgramsLoader] Loaded {len(data.get('shows', []))} shows from programs.json")
            return data
    except FileNotFoundError:
        safe_print(f"⚠️ [ProgramsLoader] programs.json not found at {file_path}")
        return {"version": "1.0", "shows": []}
    except json.JSONDecodeError as e:
        safe_print(f"❌ [ProgramsLoader] Error parsing programs.json: {e}")
        return {"version": "1.0", "shows": []}
    except Exception as e:
        safe_print(f"❌ [ProgramsLoader] Error loading programs.json: {e}")
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
                # Create a copy without provider-level fields
                program_data = {
                    'id': slug,
                    'name': show.get('name', slug),
                    'description': show.get('description', ''),
                    'channel': show.get('channel', ''),
                    'genres': show.get('genres', []),
                    'year': show.get('year', 2024),
                    'rating': show.get('rating', 'Tous publics'),
                }
                
                # Add optional fields if present
                if show.get('logo'):
                    program_data['logo'] = show['logo']
                if show.get('poster'):
                    program_data['poster'] = show['poster']
                if show.get('fanart'):
                    program_data['fanart'] = show['fanart']
                if show.get('background'):
                    program_data['background'] = show['background']
                if show.get('api_id'):
                    program_data['api_id'] = show['api_id']
                
                result[slug] = program_data
    
    safe_print(f"✅ [ProgramsLoader] Found {len(result)} shows for provider '{provider_name}'")
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
    cache.delete("programs_data")
    safe_print("🔄 [ProgramsLoader] Programs cache cleared")
