"""Entry point for ``python -m emfit``.

:mod:`emfit` (and therefore the thread pinning in :mod:`emfit._env`) has
already run by the time this module is imported, so the CLI may import numpy
freely through :mod:`emfit.studies`.
"""

import sys

from .cli import main

if __name__ == "__main__":
    sys.exit(main())
