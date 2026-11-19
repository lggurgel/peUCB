#!/bin/sh
set -e
cd /app

if [ "${DEBUG}" != "1" ]; then
  case "${SECRET_KEY}" in
    ""|build-collectstatic-only|dev-only-not-for-production)
      echo "Defina SECRET_KEY no ambiente antes de subir o serviço."
      exit 1
      ;;
  esac
fi

i=0
until python manage.py migrate --noinput; do
  i=$((i + 1))
  if [ "$i" -gt 90 ]; then
    echo "O banco não ficou pronto a tempo."
    exit 1
  fi
  sleep 1
done

python manage.py seed_demo
exec gunicorn config.wsgi:application --bind "0.0.0.0:${PORT:-8000}" --workers 1 --threads 4 --timeout 60
