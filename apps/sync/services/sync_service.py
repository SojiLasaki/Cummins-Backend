from apps.core.utils import is_connected
from apps.orders.models import Order
from supabase import create_client

SUPABASE_URL = "https://YOUR_PROJECT.supabase.co"
SUPABASE_KEY = "YOUR_SERVICE_KEY"
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

def sync_orders():
    if not is_connected():
        return

    unsynced_orders = Order.objects.filter(synced=False)
    for order in unsynced_orders:
        # Push to Supabase
        supabase.table("orders").insert({
            "id": str(order.id),
            "status": order.status,
            "approved_by": str(order.approved_by.id) if order.approved_by else None,
            "quantity": order.quantity,
            "ticket_id": str(order.ticket.id),
        }).execute()

        # Mark synced
        order.synced = True
        order.save()