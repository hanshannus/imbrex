"""Allow ``python -m imbrex``."""

import sys

from imbrex._cli import main

sys.exit(main())
