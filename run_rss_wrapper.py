#!/usr/bin/env python3
"""RSS Generator Wrapper - 載入環境變數後執行"""
import os
import subprocess
import sys

# Load .env
env_file = "/home/node/.openclaw/workspace/.env"
with open(env_file, 'r') as f:
    for line in f:
        line = line.strip()
        if line and not line.startswith('#'):
            if '=' in line:
                key, value = line.split('=', 1)
                os.environ[key] = value

# Run rss_generator.py
result = subprocess.run(
    ['/home/node/.linuxbrew/bin/python3', '/home/node/.openclaw/workspace/rss_generator.py'],
    capture_output=True, text=True,
    env={**os.environ}
)
print(result.stdout)
if result.stderr:
    print(result.stderr, file=sys.stderr)
sys.exit(result.returncode)
