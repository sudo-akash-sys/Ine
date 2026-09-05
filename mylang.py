import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

from mylang.cli import main

raise SystemExit(main())