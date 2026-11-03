"""Panel over the LogiSur -> Expreso Andino bridge."""
import sys
from pathlib import Path

# The bridge is a read-only submodule, not an installed package: make `expreso_bridge` importable once.
# Appended, not prepended: the bridge ships its own `tests` package, which must not shadow ours.
_BRIDGE = str(Path(__file__).resolve().parent.parent / "vendor" / "caso-expreso")
if _BRIDGE not in sys.path:
    sys.path.append(_BRIDGE)
