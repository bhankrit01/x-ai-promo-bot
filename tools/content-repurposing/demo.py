#!/usr/bin/env python3
"""Quick demo script — run with: python demo.py"""

import subprocess
import sys

demo_url = "https://en.wikipedia.org/wiki/Artificial_intelligence"

print("=" * 60)
print("CONTENT REPURPOSING TOOLKIT — DEMO")
print("=" * 60)
print(f"\nInput URL: {demo_url}")
print("Generating: LinkedIn + Twitter formats (professional tone)")
print("=" * 60)

cmd = [sys.executable, "repurpose.py", "--url", demo_url, "--mode", "linkedin", "--tone", "professional"]

subprocess.run(cmd)
