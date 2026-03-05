from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync

def send_notification(user, title: str, message: str, type: str, data: dict | None = None):
    """
    Create a Notification row and push it via websocket to user_{id}.
    """
    if not user:
        return None

    from .models import Notification

    notif = Notification.objects.create(
        recipient=user,
        title=title,
        message=message,
        type=type,
        data=data or {},
    )

    channel_layer = get_channel_layer()
    async_to_sync(channel_layer.group_send)(
        f"user_{user.id}",
        {
            "type": "send_notification",
            "message": {
                "id": notif.id,
                "title": title,
                "message": message,
                "type": type,
                "data": notif.data,
                "is_read": notif.is_read,
                "created_at": notif.created_at.isoformat() if notif.created_at else None,
            },
        },
    )
    return notif


def send_order_notification(user, title, message, type):
    # Backwards compatible wrapper
    return send_notification(user, title, message, type)
