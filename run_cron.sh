#!/bin/bash
cd /app
export DATABASE_HOST=${DATABASE_HOST:-db}
export DATABASE_NAME=${DATABASE_NAME:-tenant_db}
export DATABASE_USER=${DATABASE_USER:-postgres}
export DATABASE_PASSWORD=${DATABASE_PASSWORD:-password}
export DJANGO_SETTINGS_MODULE=${DJANGO_SETTINGS_MODULE:-config.settings}
exec /usr/local/bin/python /app/manage.py "$@"

