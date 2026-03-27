#!/bin/bash
export GOOGLE_SHEETS_CREDENTIALS="$GOOGLE_SHEETS_CREDENTIALS"
export GOOGLE_SHEETS_ID="$GOOGLE_SHEETS_ID"
export GITHUB_TOKEN="$GITHUB_TOKEN"
export GITHUB_REPO="$GITHUB_REPO"
export GEMINI_API_KEY="$GEMINI_API_KEY"
python3 /home/node/.openclaw/workspace/external_scout.py
