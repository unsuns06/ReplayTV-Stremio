from typing import Type, Dict, Optional
from app.providers.base_provider import BaseProvider
from app.providers.fr.francetv import FranceTVProvider
from app.providers.fr.mytf1 import MyTF1Provider
from app.providers.fr.sixplay import SixPlayProvider
from app.providers.ca.cbc import CBCProvider

# Map provider keys to their implementation classes
PROVIDER_CLASSES: Dict[str, Type[BaseProvider]] = {
    "francetv": FranceTVProvider,
    "mytf1": MyTF1Provider,
    "6play": SixPlayProvider,
    "cbc": CBCProvider,
}

def get_provider_class(key: str) -> Optional[Type[BaseProvider]]:
    """Get the provider class for a given key."""
    return PROVIDER_CLASSES.get(key)
