import json
import re

def parse_lenient_json(json_string: str):
    """
    Parses a JSON string that may contain trailing commas.
    """
    print(f"Attempting to parse JSON string: {json_string[:200]}...") # Print first 200 chars
    json_string = re.sub(r",\s*([\}\]])", r"\1", json_string)
    return json.loads(json_string)