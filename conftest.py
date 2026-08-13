import sys
from pathlib import Path
 
# Applies to every test file pytest collects under evals/, regardless of
# which subfolder (tests/, checks/, ...) it lives in - conftest.py files
# are auto-loaded for the whole tree beneath them.
sys.path.insert(0, str(Path(__file__).resolve().parent))
 