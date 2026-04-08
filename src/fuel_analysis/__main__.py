"""Allow running as: python -m fuel_analysis <command>"""

import sys
from .cli import main

sys.exit(main())
