release: python manage.py migrate --noinput --settings=config.settings_production
web: gunicorn config.wsgi:application --env DJANGO_SETTINGS_MODULE=config.settings_production --log-file -
worker: python manage.py process_jobs --settings=config.settings_production
