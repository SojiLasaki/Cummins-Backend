from __future__ import annotations

import secrets

from django.utils import timezone

from apps.tickets.models import Ticket


def generate_ticket_id(prefix: str = "TK") -> str:
    """
    Generate a short human-readable ticket identifier with collision checks.
    """
    normalized_prefix = (prefix or "TK").strip().upper() or "TK"
    for _ in range(10):
        stamp = timezone.now().strftime("%m%d%H%M%S")
        suffix = secrets.token_hex(2).upper()
        candidate = f"{normalized_prefix}-{stamp}-{suffix}"
        if not Ticket.objects.filter(ticket_id=candidate).exists():
            return candidate
    return f"{normalized_prefix}-{timezone.now().strftime('%m%d%H%M%S%f')}"
