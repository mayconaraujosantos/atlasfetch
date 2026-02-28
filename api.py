"""
API REST - ponto de entrada.
Delega para a aplicação Clean Architecture.
"""

import sys
from pathlib import Path

# Garante que src/ esteja no path (sem precisar de pip install -e)
_src = Path(__file__).parent / "src"
if _src.exists() and str(_src) not in sys.path:
    sys.path.insert(0, str(_src))

from atlasfetch.api.app import app

__all__ = ["app"]
