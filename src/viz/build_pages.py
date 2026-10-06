#!/usr/bin/env python3
import sys
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

def main() -> int:
    source = ROOT / "index.html"
    dest = ROOT / "docs" / "index.html"
    
    if not source.exists():
        return 1
        
    dest.parent.mkdir(exist_ok=True)
    shutil.copy2(source, dest)
    print("Copied")
    return 0

if __name__ == "__main__":
    sys.exit(main())
