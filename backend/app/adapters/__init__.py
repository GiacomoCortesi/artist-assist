"""Platform adapters package."""

# Register concrete adapters
from app.adapters import deezer as _deezer  # noqa: F401
from app.adapters import facebook as _facebook  # noqa: F401
from app.adapters import fake as _fake  # noqa: F401
from app.adapters import instagram as _instagram  # noqa: F401
from app.adapters import soundcloud as _soundcloud  # noqa: F401
from app.adapters import spotify as _spotify  # noqa: F401
from app.adapters import threads as _threads  # noqa: F401
from app.adapters import tiktok as _tiktok  # noqa: F401
from app.adapters import youtube as _youtube  # noqa: F401
from app.adapters.base import list_registered_sources

__all__ = [
    "list_registered_sources",
]
