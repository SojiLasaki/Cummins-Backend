from __future__ import annotations

from django.db import transaction
from django.db.models.signals import post_save
from django.dispatch import receiver

from apps.assets.models import Asset
from apps.notifications.utils import send_notification


@receiver(post_save, sender=Asset)
def notify_customer_on_asset_update(sender, instance: Asset, created: bool, **kwargs):
    customer = getattr(instance, "customer", None)
    user = getattr(customer, "user", None) if customer else None
    if not user:
        return

    def payload():
        return {
            "asset_id": str(instance.id),
            "product_id": instance.product_id,
            "asset_type": instance.asset_type,
            "customer_id": str(customer.id) if customer else None,
        }

    if created:
        transaction.on_commit(
            lambda: send_notification(
                user,
                "Asset Added",
                f"Asset {instance.product_id} has been added to your account.",
                "asset_updated",
                data=payload(),
            )
        )
    else:
        transaction.on_commit(
            lambda: send_notification(
                user,
                "Asset Updated",
                f"Asset {instance.product_id} has been updated.",
                "asset_updated",
                data=payload(),
            )
        )

