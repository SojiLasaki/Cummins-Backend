from __future__ import annotations

from apps.technicians.models import TechnicianProfile

def calculate_experience_score(tech: TechnicianProfile, ticket) -> float:
    """
    Calculate a technician score using fields that actually exist on TechnicianProfile.

    Higher is better. Returns 0 for technicians that should be disqualified.
    """
    severity = getattr(ticket, "severity", 2) or 2  # Ticket.severity is an int (1-4)
    expertise = (getattr(tech, "expertise", "") or "").lower()

    # Disqualify for high/severe incidents unless experienced enough.
    if severity >= 3 and not (tech.total_years_experience >= 5 or expertise == "senior"):
        return 0.0

    expertise_bonus = {"junior": 0.0, "mid": 5.0, "senior": 10.0}.get(expertise, 0.0)
    certifications_bonus = float(tech.certifications.count()) * 1.0

    return (
        (tech.performance_rating * 20.0)
        + (tech.total_years_experience * 2.0)
        + (tech.total_jobs_completed * 0.1)
        + (tech.skill_score * 5.0)
        + expertise_bonus
        + certifications_bonus
    )


def assign_best_technician(ticket):
    # Step 1: Filter available technicians with correct specialization
    technicians = TechnicianProfile.objects.filter(
        specialization=ticket.specialization,
        status="available",
    )

    if not technicians.exists():
        return None  # No eligible technicians

    # Step 2: Score each technician
    scored_techs = [(tech, calculate_experience_score(tech, ticket)) for tech in technicians]
    # Drop disqualified technicians (score <= 0.0)
    scored_techs = [(tech, score) for (tech, score) in scored_techs if score > 0.0]

    if not scored_techs:
        return None  # All available technicians were disqualified

    # Step 3: Sort descending
    scored_techs.sort(key=lambda x: x[1], reverse=True)

    # Step 4: Return top technician
    return scored_techs[0][0] if scored_techs else None