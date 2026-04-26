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

PROGRAMS_FILE_CACHE_TTL = 3600  # 1 hour

# Known valid providers — used by the schema validator
_KNOWN_PROVIDERS = {"6play", "francetv", "mytf1", "cbc"}

# Required fields on every show entry
_SHOW_REQUIRED_FIELDS = {"provider", "slug", "name"}


def _validate_programs_data(data: Dict) -> List[str]:
    """Validate the structure of a loaded programs.json dict.

    Uses built-in checks only — no external schema library required.  All
    violations are returned as human-readable warning strings; the caller
    decides whether to log or raise them.

    Args:
        data: The parsed JSON dict from programs.json.

    Returns:
        List of warning strings; empty if the data is valid.
    """
    warnings: List[str] = []

    if not isinstance(data, dict):
        return ["Root element must be a JSON object"]

    if "version" not in data:
        warnings.append("Missing 'version' field")
    elif not isinstance(data["version"], str):
        warnings.append(f"'version' must be a string, got {type(data['version']).__name__}")

    if "shows" not in data:
        warnings.append("Missing 'shows' array")
        return warnings

    if not isinstance(data["shows"], list):
        warnings.append(f"'shows' must be an array, got {type(data['shows']).__name__}")
        return warnings

    for i, show in enumerate(data["shows"]):
        prefix = f"shows[{i}]"
        if not isinstance(show, dict):
            warnings.append(f"{prefix}: entry must be a JSON object")
            continue

        for field in _SHOW_REQUIRED_FIELDS:
            if field not in show:
                warnings.append(f"{prefix}: missing required field '{field}'")

        provider = show.get("provider")
        if provider and provider not in _KNOWN_PROVIDERS:
            warnings.append(
                f"{prefix}: unknown provider '{provider}' "
                f"(expected one of {sorted(_KNOWN_PROVIDERS)})"
            )

        for str_field in ("slug", "name", "description", "channel", "rating"):
            val = show.get(str_field)
            if val is not None and not isinstance(val, str):
                warnings.append(f"{prefix}.{str_field}: expected string, got {type(val).__name__}")

        for url_field in ("logo", "poster", "background", "fanart"):
            val = show.get(url_field)
            if val is not None and not isinstance(val, str):
                warnings.append(f"{prefix}.{url_field}: expected string URL, got {type(val).__name__}")

        if "year" in show and not isinstance(show["year"], int):
            warnings.append(f"{prefix}.year: expected integer, got {type(show['year']).__name__}")

        if "enabled" in show and not isinstance(show["enabled"], bool):
            warnings.append(f"{prefix}.enabled: expected boolean, got {type(show['enabled']).__name__}")

        if "genres" in show and not isinstance(show["genres"], list):
            warnings.append(f"{prefix}.genres: expected array, got {type(show['genres']).__name__}")

    return warnings


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
            warnings = _validate_programs_data(data)
            for w in warnings:
                safe_print(f"⚠️ [ProgramsLoader] programs.json validation: {w}")
            cache.set("programs_data", data, ttl=PROGRAMS_FILE_CACHE_TTL)
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
