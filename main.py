"""
CLI - ponto de entrada.
Delega para a aplicação Clean Architecture.
"""

import sys
from pathlib import Path

# Garante que src/ esteja no path
_src = Path(__file__).parent / "src"
if _src.exists() and str(_src) not in sys.path:
    sys.path.insert(0, str(_src))

from atlasfetch.cli.main import main

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        import logging
        logging.getLogger(__name__).exception("Erro fatal: %s", e)
        raise
