#!/bin/bash

echo "Creating migrations for all apps (if needed)..."
python manage.py makemigrations || echo "Note: Some migrations may already exist or database not ready yet"

echo "Applying migrations..."
python manage.py migrate_schemas --shared
python manage.py migrate_schemas --tenant

echo "Starting django-q2 cluster worker in background..."
python manage.py qcluster &

echo "Starting Django server..."
python manage.py runserver 0.0.0.0:8000