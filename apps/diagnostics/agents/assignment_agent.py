from apps.technicians.models import TechnicianProfile

class AssignmentAgent:

    def assign(self, report):
        available_techs = TechnicianProfile.objects.filter(is_available=True)

        if not available_techs.exists():
            raise Exception("No technicians available")

        # Example: choose least busy
        technician = available_techs.order_by("current_workload").first()

        technician.current_workload += 1
        technician.save()

        return technician