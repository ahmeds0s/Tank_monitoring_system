#!/bin/bash
lsof -ti :8000 | xargs -r kill -9
nohup python -m uvicorn main:app --port 8000 --host 0.0.0.0 --reload --ssl-keyfile=key.pem --ssl-certfile=cert.pem >log.txt 2>&1 &
