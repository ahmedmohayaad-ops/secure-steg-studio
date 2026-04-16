"""
Secure Steganography Studio — Entry Point
Run this file from anywhere:  python main.py
"""
import sys
import os

# Ensure the directory that CONTAINS steg_studio/ is on sys.path
# so that `from steg_studio.xxx import yyy` always resolves.
ROOT = os.path.dirname(os.path.abspath(__file__))
PARENT = os.path.dirname(ROOT)
if PARENT not in sys.path:
    sys.path.insert(0, PARENT)

from steg_studio.gui.app import run   # noqa: E402  (import after path fix)

if __name__ == "__main__":
    run()
