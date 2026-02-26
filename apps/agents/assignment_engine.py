from datetime import date
from apps.technicians.models import TechnicianProfile

# apps/technicians/services/assignment_engine.py
from datetime import date
from apps.technicians.models import TechnicianProfile

def calculate_experience_score(tech: TechnicianProfile, ticket) -> float:
    """
    Calculate technician experience score based on weights:
    0.35 Specialization, 0.30 Overall experience, 0.20 Station tenure, 0.15 Performance
    """
    # --- Specialization Score ---
    spec_jobs = 0
    if ticket.specialization == "Engine":
        spec_jobs = tech.engine_jobs
    elif ticket.specialization == "Electrical":
        spec_jobs = tech.electrical_jobs

    total_jobs = tech.total_jobs_completed or 1
    spec_score = (spec_jobs / total_jobs) * 100

    # --- Overall Experience Score ---
    overall_score = (tech.total_years_experience * 5) + (tech.total_jobs_completed * 0.1)

    # --- Station Tenure Score ---
    station_years = 0
    if tech.date_joined_station:
        station_years = (date.today() - tech.date_joined_station).days / 365
    station_score = station_years * 5

    # --- Performance Score ---
    performance_score = (tech.performance_rating / 5) * 100

    # --- Weighted Sum ---
    final_score = (
        0.35 * spec_score +
        0.30 * overall_score +
        0.20 * station_score +
        0.15 * performance_score
    )

    # --- Optional Load Balancing ---
    active_jobs = tech.jobs.filter(date_completed__isnull=True).count()
    final_score -= active_jobs * 5

    # --- Severity Restriction ---
    if ticket.severity.lower() in ['high', 'severe']:
        if tech.total_years_experience < 5 or spec_jobs < 50:
            final_score = 0  # disqualify

    return final_score


def assign_best_technician(ticket):
    # Step 1: Filter available technicians with correct specialization
    technicians = TechnicianProfile.objects.filter(
        specialization=ticket.specialization,
        status='Available'
    )

    if not technicians.exists():
        return None  # No eligible technicians

    # Step 2: Score each technician
    scored_techs = [(tech, calculate_experience_score(tech, ticket)) for tech in technicians]

    # Step 3: Sort descending
    scored_techs.sort(key=lambda x: x[1], reverse=True)

    # Step 4: Return top technician
    return scored_techs[0][0] if scored_techs else None