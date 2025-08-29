def parse_channel_id(channel_id: str) -> dict:
    """
    Parse a channel ID in the format cutam:fr:{provider}:{channel_slug}
    Returns a dictionary with the components
    """
    parts = channel_id.split(":")
    if len(parts) >= 4 and parts[0] == "cutam" and parts[1] == "fr":
        return {
            "provider": parts[2],
            "channel_slug": ":".join(parts[3:])  # In case the slug contains colons
        }
    return {}

def parse_program_id(program_id: str) -> dict:
    """
    Parse a program ID in the format cutam:fr:{provider}:prog:{program_slug}
    Returns a dictionary with the components
    """
    parts = program_id.split(":")
    if len(parts) >= 5 and parts[0] == "cutam" and parts[1] == "fr" and parts[3] == "prog":
        return {
            "provider": parts[2],
            "program_slug": ":".join(parts[4:])  # In case the slug contains colons
        }
    return {}

def parse_episode_id(episode_id: str) -> dict:
    """
    Parse an episode ID in the format cutam:fr:{provider}:ep:{program_slug}:{season}:{episode}
    Returns a dictionary with the components
    """
    parts = episode_id.split(":")
    if len(parts) >= 7 and parts[0] == "cutam" and parts[1] == "fr" and parts[3] == "ep":
        return {
            "provider": parts[2],
            "program_slug": parts[4],
            "season": int(parts[5]) if parts[5].isdigit() else parts[5],
            "episode": int(parts[6]) if parts[6].isdigit() else parts[6]
        }
    return {}