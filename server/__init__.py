"""Video server package.

``VideoServer`` is exposed lazily so that running ``python -m server.server``
doesn't pre-import the module and trigger a RuntimeWarning.
"""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .server import VideoServer

__all__ = ["VideoServer"]


def __getattr__(name: str):
    if name == "VideoServer":
        from .server import VideoServer as _VideoServer
        return _VideoServer
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
