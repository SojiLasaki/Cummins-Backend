from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync

def send_order_notification(user, title, message, type):
    if not user:
        return
    channel_layer = get_channel_layer()
    async_to_sync(channel_layer.group_send)(
        f"user_{user.id}",
        {
            "type": "send_notification",
            "message": {
                "title": title,
                "message": message,
                "type": type,
            },
        },
    )
