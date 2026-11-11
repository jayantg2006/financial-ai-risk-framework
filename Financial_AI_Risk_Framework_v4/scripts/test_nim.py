from __future__ import annotations
import subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
raise SystemExit(subprocess.call([sys.executable,str(ROOT/'scripts/test_nim_api.py'),*sys.argv[1:]]))
