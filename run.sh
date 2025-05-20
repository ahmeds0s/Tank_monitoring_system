#!/bin/bash
lsof -ti :8000 | xargs -r kill -9
nohup python -m uvicorn main:app --port 8000 --host 0.0.0.0 --workers 2 >log.txt 2>&1 &
