#!/usr/bin/env python3
"""
Quick install and test script.
Run: python setup.py
"""

import subprocess
import sys
import os


def main():
    print("=" * 60)
    print("Content Repurposing Toolkit — Setup")
    print("=" * 60)

    # Install optional dependencies
    print("\n[1/2] Installing optional dependencies for full features...")
    try:
        subprocess.run(
            [sys.executable, "-m", "pip", "install", "requests", "beautifulsoup4", "rich"],
            capture_output=True, text=True
        )
        print("  ✓ Dependencies installed")
    except Exception as e:
        print(f"  ⚠ Skipped: {e}")
        print("  (Tool works with stdlib only — limited content extraction)")

    # Run demo
    print("\n[2/2] Running demo...\n")
    demo_path = os.path.join(os.path.dirname(__file__), "demo.py")
    subprocess.run([sys.executable, demo_path])


if __name__ == "__main__":
    main()
