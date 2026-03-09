release: python manage.py migrate && python manage.py collectstatic --noinput
web: gunicorn breakthru.wsgi:application
