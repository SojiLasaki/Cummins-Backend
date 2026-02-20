"""
ASGI config for breakthru project.

It exposes the ASGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/5.1/howto/deployment/asgi/
"""
import os
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.auth import AuthMiddlewareStack
from django.core.asgi import get_asgi_application
import apps.notifications.routing

# os.environ.setdefault("DJANGO_SETTINGS_MODULE", "breakthru.settings")
# change to productioin if not in dev
os.environ.setdefault(
    'DJANGO_SETTINGS_MODULE',
    'breakthru.settings.development'
)

# application = get_asgi_application()
application = ProtocolTypeRouter({
    "http": get_asgi_application(),
    "websocket": AuthMiddlewareStack(
        URLRouter(
            apps.notifications.routing.websocket_urlpatterns
        )
    ),
})