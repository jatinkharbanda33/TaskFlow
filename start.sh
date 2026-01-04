#!/bin/bash

touch /app/cron.log
chmod 666 /app/cron.log

echo "Removing old cron jobs..."
python manage.py crontab remove 2>/dev/null || true

echo "Adding cron jobs..."
python manage.py crontab add

echo "Starting cron service..."
service cron start

echo "Creating migrations for all apps (if needed)..."
python manage.py makemigrations || echo "Note: Some migrations may already exist or database not ready yet"

echo "Applying migrations..."
python manage.py migrate_schemas --shared
python manage.py migrate_schemas --tenant

echo "Starting Django server..."
python manage.py runserver 0.0.0.0:8000