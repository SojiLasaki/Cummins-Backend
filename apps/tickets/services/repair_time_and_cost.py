"""
Repair time and maintenance cost calculations for tickets.

Definitions (used in API and docs):
- Predicted repair time: estimated on-site time to fix the issue (minutes).
  Stored as Ticket.estimated_resolution_time_minutes.
- Predicted commute time: round-trip travel time technician base → job site → base (minutes).
  Stored as Ticket.predicted_commute_time_minutes.
- Predicted total time to fix (including commute): repair time + commute time (minutes).
  Used for labor cost: (predicted_total_minutes / 60) * technician hourly rate.
"""
from decimal import Decimal
from django.db.models import Avg


# --- Per-ticket helpers ---

def get_predicted_repair_time_minutes(ticket):
    """
    Predicted on-site repair time in minutes (time to fix the issue at the job site).
    Returns None if not set.
    """
    return getattr(ticket, "estimated_resolution_time_minutes", None)


def get_predicted_commute_time_minutes(ticket):
    """
    Predicted round-trip commute time in minutes (technician base to job site and back).
    Returns 0 if not set (so total time = repair only).
    """
    val = getattr(ticket, "predicted_commute_time_minutes", None)
    return val if val is not None else 0


def get_predicted_total_time_minutes(ticket):
    """
    Predicted total time to fix the issue, including commute (minutes).
    = predicted repair time (on-site) + predicted commute time (round-trip).
    Returns None if repair time is not set; otherwise repair + commute (commute defaults to 0).
    """
    repair = get_predicted_repair_time_minutes(ticket)
    if repair is None:
        return None
    commute = get_predicted_commute_time_minutes(ticket)
    return repair + commute


def get_technician_hourly_rate(ticket):
    """Technician hourly rate for this ticket, or None if unassigned / no rate."""
    tech = getattr(ticket, "assigned_technician", None)
    if not tech:
        return None
    rate = getattr(tech, "hourly_rate", None)
    return rate if rate is not None else None


def get_predicted_labor_cost(ticket):
    """
    Predicted labor cost for this ticket: (predicted_total_time_minutes / 60) * technician hourly rate.
    Returns None if predicted total time or hourly rate is missing.
    """
    total_min = get_predicted_total_time_minutes(ticket)
    rate = get_technician_hourly_rate(ticket)
    if total_min is None or rate is None:
        return None
    hours = Decimal(total_min) / Decimal(60)
    return round(hours * Decimal(str(rate)), 2)


def get_maintenance_cost_breakdown(ticket):
    """
    Detailed maintenance cost breakdown for a single ticket, with clear descriptions.
    Suitable for API response and UI display.
    """
    repair_min = get_predicted_repair_time_minutes(ticket)
    commute_min = get_predicted_commute_time_minutes(ticket)
    total_min = get_predicted_total_time_minutes(ticket)
    hourly_rate = get_technician_hourly_rate(ticket)
    labor_cost = get_predicted_labor_cost(ticket)

    return {
        "description": (
            "Predicted time to fix = on-site repair time + round-trip commute time. "
            "Labor cost = (predicted total hours) × technician hourly rate."
        ),
        "predicted_repair_time_minutes": repair_min,
        "predicted_repair_time_label": "Predicted on-site repair time (minutes)",
        "predicted_commute_time_minutes": commute_min if commute_min else None,
        "predicted_commute_time_label": "Predicted round-trip commute time (minutes)",
        "predicted_total_time_minutes": total_min,
        "predicted_total_time_label": "Predicted total time to fix, including commute (minutes)",
        "technician_hourly_rate": float(hourly_rate) if hourly_rate is not None else None,
        "technician_hourly_rate_label": "Technician pay per hour (used for labor cost)",
        "predicted_labor_cost": float(labor_cost) if labor_cost is not None else None,
        "predicted_labor_cost_label": "Predicted labor cost (total hours × hourly rate)",
    }


# --- Aggregates (average repair time) ---

def get_average_repair_time_minutes(queryset, use_actual=False):
    """
    Average repair time in minutes over the given ticket queryset.
    use_actual=False: average of estimated_resolution_time_minutes (predicted).
    use_actual=True: average of actual_resolution_time_minutes (only tickets that have it set).
    Returns None if no values.
    """
    field = "actual_resolution_time_minutes" if use_actual else "estimated_resolution_time_minutes"
    qs = queryset.filter(**{f"{field}__isnull": False})
    result = qs.aggregate(avg=Avg(field))
    avg = result.get("avg")
    return round(avg, 2) if avg is not None else None


def get_repair_time_stats(queryset):
    """
    Aggregate stats for average repair time (predicted and actual) over a ticket queryset.
    """
    pred_avg = get_average_repair_time_minutes(queryset, use_actual=False)
    actual_avg = get_average_repair_time_minutes(queryset, use_actual=True)
    with_estimated = queryset.filter(estimated_resolution_time_minutes__isnull=False).count()
    with_actual = queryset.filter(actual_resolution_time_minutes__isnull=False).count()
    return {
        "average_predicted_repair_time_minutes": pred_avg,
        "average_actual_repair_time_minutes": actual_avg,
        "tickets_with_predicted_time": with_estimated,
        "tickets_with_actual_time": with_actual,
        "description": (
            "Average predicted = mean of estimated_resolution_time_minutes. "
            "Average actual = mean of actual_resolution_time_minutes (completed jobs)."
        ),
    }
