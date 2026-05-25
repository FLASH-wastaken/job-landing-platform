#!/bin/bash
echo "Starting with PORT=${PORT:-8000}"
exec gunicorn backend.main:app \
  --workers 2 \
  --worker-class uvicorn.workers.UvicornWorker \
  --bind "0.0.0.0:${PORT:-8000}" \
  --timeout 120
