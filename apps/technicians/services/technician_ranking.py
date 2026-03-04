"""
Technician ranking for task assignment.

Ranks technicians by:
- Years of experience (fitness for job complexity)
- Job severity (minimum experience/expertise required per severity)
- Completion rate (completed tickets / assigned tickets)

Severity tiers (Ticket.severity 1–4):
- 1 Low: any technician
- 2 Medium: prefer 1+ years
- 3 High: require 3+ years or mid+ expertise
- 4 Severe: require 5+ years or senior expertise
"""

from __future__ import annotations

from apps.technicians.models import TechnicianProfile
from apps.tickets.models import Ticket


# Severity (1–4) -> (min_years, allowed_expertise_levels)
# expertise: junior=0, mid=1, senior=2
SEVERITY_REQUIREMENTS = {
    1: (0.0, ["junior", "mid", "senior"]),
    2: (1.0, ["junior", "mid", "senior"]),
    3: (3.0, ["mid", "senior"]),
    4: (5.0, ["senior"]),
}

EXPERTISE_ORDER = {"junior": 0, "mid": 1, "senior": 2}

# Weights for final score (tune as needed)
# Sum ~= 1.0
WEIGHT_LOCATION = 0.30            # how close technician is to customer
WEIGHT_SEVERITY_EXPERIENCE = 0.25 # history of high‑severity work
WEIGHT_SEVERITY_FIT = 0.20        # expertise/years vs current severity
WEIGHT_YEARS = 0.15               # general experience
WEIGHT_COMPLETION_RATE = 0.10     # reliability


def get_completion_rate(technician: TechnicianProfile) -> float:
    """
    Completion rate = completed_or_closed / assigned (ever).
    Returns 0.0–1.0; 1.0 if no assignments yet (no failure history).
    """
    assigned = Ticket.objects.filter(assigned_technician=technician)
    total = assigned.count()
    if total == 0:
        return 1.0
    completed = assigned.filter(status__in=("completed", "closed")).count()
    return completed / total


def get_completion_rates_bulk(technicians):
    """
    Batch-fetch completion rates for a list of technicians to avoid N+1.
    Returns dict: technician_id -> float (0.0–1.0).
    """
    from django.db.models import Count

    ids = [t.pk for t in technicians]
    # Total assigned per technician
    totals = (
        Ticket.objects.filter(assigned_technician_id__in=ids)
        .values("assigned_technician_id")
        .annotate(total=Count("id"))
    )
    total_map = {r["assigned_technician_id"]: r["total"] for r in totals}

    completed = (
        Ticket.objects.filter(
            assigned_technician_id__in=ids,
            status__in=("completed", "closed"),
        )
        .values("assigned_technician_id")
        .annotate(done=Count("id"))
    )
    done_map = {r["assigned_technician_id"]: r["done"] for r in completed}

    out = {}
    for tid in ids:
        t = total_map.get(tid) or 0
        if t == 0:
            out[tid] = 1.0
        else:
            out[tid] = (done_map.get(tid) or 0) / t
    return out


def get_severity_experience_bulk(technicians):
    """
    Severity-weighted experience:
    Sum of severities for completed/closed tickets per technician.

    E.g. one severity-4 job counts more than one severity-1 job.
    Returns dict: technician_id -> severity_points (float).
    """
    from django.db.models import Sum

    ids = [t.pk for t in technicians]
    rows = (
        Ticket.objects.filter(
            assigned_technician_id__in=ids,
            status__in=("completed", "closed"),
        )
        .values("assigned_technician_id")
        .annotate(points=Sum("severity"))
    )
    return {r["assigned_technician_id"]: float(r["points"] or 0.0) for r in rows}


def severity_experience_score(points: float, ticket_severity: int) -> float:
    """
    Map severity_points into 0–1.

    We give more credit when the technician has handled many
    equal-or-higher severity jobs. Cap so a very long history
    does not dominate everything.
    """
    if points <= 0:
        return 0.0

    # Each completed job contributes its severity (1–4).
    # 40 points ~= 10 high-severity jobs or 20 medium ones.
    base = min(1.0, points / 40.0)

    # Slight boost if current severity is high.
    if ticket_severity >= 4:
        base = min(1.0, base * 1.1)
    elif ticket_severity >= 3:
        base = min(1.0, base * 1.05)
    return base


def location_score(technician: TechnicianProfile, ticket: Ticket) -> float:
    """
    Rough 'closeness' score based on customer vs technician station address.

    1.0  -> same city + state + country
    0.7  -> same state + country
    0.4  -> same country
    0.0  -> unknown / no match
    """
    customer = getattr(ticket, "customer", None)
    station = getattr(technician, "station", None)
    if not customer or not station:
        return 0.0

    def norm(val: str | None) -> str:
        return (val or "").strip().lower()

    c_city = norm(getattr(customer, "city", None))
    c_state = norm(getattr(customer, "state", None))
    c_country = norm(getattr(customer, "country", None))

    s_city = norm(getattr(station, "city", None))
    s_state = norm(getattr(station, "state", None))
    s_country = norm(getattr(station, "country", None))

    if c_country and s_country and c_country == s_country:
        if c_state and s_state and c_state == s_state:
            if c_city and s_city and c_city == s_city:
                return 1.0
            return 0.7
        return 0.4
    return 0.0


def severity_eligible(technician: TechnicianProfile, severity: int) -> bool:
    """True if technician meets minimum years and expertise for this severity."""
    min_years, allowed_expertise = SEVERITY_REQUIREMENTS.get(
        severity, (0.0, ["junior", "mid", "senior"])
    )
    years = getattr(technician, "total_years_experience", 0) or 0
    expertise = (getattr(technician, "expertise", "") or "junior").lower()
    if expertise not in allowed_expertise:
        return False
    # Senior can qualify by title even with fewer years; otherwise require min_years
    if expertise == "senior":
        return years >= max(0, min_years - 2)  # e.g. severity 4: 3+ years for senior
    return years >= min_years


def severity_fitness_score(technician: TechnicianProfile, severity: int) -> float:
    """
    0.0 = ineligible, 1.0 = ideal for this severity.
    Uses years and expertise level.
    """
    min_years, allowed_expertise = SEVERITY_REQUIREMENTS.get(
        severity, (0.0, ["junior", "mid", "senior"])
    )
    years = getattr(technician, "total_years_experience", 0) or 0
    expertise = (getattr(technician, "expertise", "") or "junior").lower()

    if expertise not in allowed_expertise or years < min_years:
        return 0.0

    # Scale: at min_years = 0.5, then cap at 1.0 with more years
    year_score = 0.5 + min(0.5, (years - min_years) / 10.0) if min_years else min(1.0, years / 5.0)
    level = EXPERTISE_ORDER.get(expertise, 0) / 2.0  # 0, 0.5, 1.0
    return min(1.0, (year_score + level) / 1.5)


def years_score(technician: TechnicianProfile) -> float:
    """Normalize years into 0–1 (e.g. 0–15+ years)."""
    years = getattr(technician, "total_years_experience", 0) or 0
    return min(1.0, years / 15.0)


def calculate_rank_score(
    technician: TechnicianProfile,
    ticket,
    completion_rate: float,
    location: float,
    severity_experience: float,
) -> float:
    """
    Single combined rank score for this technician for this ticket.
    Higher is better. Returns 0.0 if not eligible for this severity.
    """
    severity = getattr(ticket, "severity", 2) or 2
    if not severity_eligible(technician, severity):
        return 0.0

    s_severity = severity_fitness_score(technician, severity)
    s_years = years_score(technician)
    s_location = max(0.0, min(1.0, location))
    s_severity_exp = max(0.0, min(1.0, severity_experience))
    # completion_rate already 0–1

    return (
        WEIGHT_LOCATION * s_location
        + WEIGHT_SEVERITY_EXPERIENCE * s_severity_exp
        + WEIGHT_SEVERITY_FIT * s_severity
        + WEIGHT_YEARS * s_years
        + WEIGHT_COMPLETION_RATE * completion_rate
    )


def rank_technicians_for_ticket(ticket):
    """
    Returns list of (technician, score) for technicians who are available,
    match specialization, and are eligible for the ticket severity.
    Sorted by score descending; score 0 means ineligible (excluded).
    """
    from apps.technicians.models import TechnicianProfile

    technicians = list(
        TechnicianProfile.objects.filter(
            specialization=ticket.specialization,
            status="available",
        )
    )
    if not technicians:
        return []

    completion_rates = get_completion_rates_bulk(technicians)
    severity_points = get_severity_experience_bulk(technicians)
    scored = []
    ticket_severity = getattr(ticket, "severity", 2) or 2

    for tech in technicians:
        rate = completion_rates.get(tech.pk, 1.0)
        sev_points = severity_points.get(tech.pk, 0.0)
        sev_exp_score = severity_experience_score(sev_points, ticket_severity)
        loc_score = location_score(tech, ticket)
        score = calculate_rank_score(tech, ticket, rate, loc_score, sev_exp_score)
        if score > 0:
            scored.append((tech, score))

    scored.sort(key=lambda x: x[1], reverse=True)
    return scored


def get_best_technician_for_ticket(ticket):
    """
    Returns the top-ranked available technician for this ticket, or None.
    """
    ranked = rank_technicians_for_ticket(ticket)
    return ranked[0][0] if ranked else None
