release: python manage.py migrate --noinput --settings=config.settings_local
web: gunicorn config.wsgi:application --env DJANGO_SETTINGS_MODULE=config.settings_local --log-file -
worker: python manage.py process_jobs --settings=config.settings_local
