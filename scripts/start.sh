#!/bin/sh
set -e

python /app/src/manage.py migrate --no-input

# el API solo dentro del contenedor; hacia fuera responde Nginx (deploy/azure/nginx.conf)
export GRANIAN_HOST=127.0.0.1
export GRANIAN_PORT=8000

nginx -e stderr
exec granian api_core.asgi:application --access-log
