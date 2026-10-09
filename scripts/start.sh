#!/bin/sh
set -e
python /app/src/manage.py migrate --no-input
exec granian api_core.asgi:application --access-log
