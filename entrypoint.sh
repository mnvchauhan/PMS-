#!/bin/sh
set -e

echo "=========================================="
echo "🏨 Grand Horizon Hotel Front Office PMS"
echo "=========================================="

# Ensure data directory exists if DB_PATH points to it
if [ -n "$DB_PATH" ]; then
    DB_DIR=$(dirname "$DB_PATH")
    mkdir -p "$DB_DIR"
fi

echo "==> Running database migrations..."
python manage.py migrate --noinput

# Seed sample data if requested (default to true for initial easy setup)
if [ "$SEED_DATA" = "true" ] || [ "$SEED_DATA" = "1" ]; then
    echo "==> Seeding hotel front office initial data..."
    python manage.py seed_pms_data || echo "==> Sample data already present or seeding skipped."
fi

echo "==> Starting Gunicorn on 0.0.0.0:8000..."
exec gunicorn config.wsgi:application \
    --bind 0.0.0.0:8000 \
    --workers ${GUNICORN_WORKERS:-3} \
    --timeout ${GUNICORN_TIMEOUT:-120} \
    --access-logfile - \
    --error-logfile -
