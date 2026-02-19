"""
ASGI config for breakthru project.

It exposes the ASGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/5.1/howto/deployment/asgi/
"""

import os

from django.core.asgi import get_asgi_application

# os.environ.setdefault("DJANGO_SETTINGS_MODULE", "breakthru.settings")
# change to productioin if not in dev
os.environ.setdefault(
    'DJANGO_SETTINGS_MODULE',
    'breakthru.settings.development'
)

application = get_asgi_application()
