"""
Assigns the best available technician to a ticket using the technician ranking system.

Ranking uses: years of experience, job severity fitness, and completion rate.
"""

from __future__ import annotations

from apps.technicians.services.technician_ranking import get_best_technician_for_ticket


def assign_best_technician(ticket):
    """
    Return the top-ranked available technician for this ticket, or None.
    Uses technician rank: years, severity eligibility, and completion rate.
    """
    return get_best_technician_for_ticket(ticket)