# core/services/system_orchestrator.py

from apps.diagnostics.models import DiagnosticReport
from apps.technicians.models import TechnicianProfile
from apps.diagnostics.agents.severity_agent import SeverityAgent
from apps.diagnostics.agents.assignment_agent import AssignmentAgent


class SystemOrchestrator:

    def __init__(self):
        self.severity_agent = SeverityAgent()
        self.assignment_agent = AssignmentAgent()

    def run_full_diagnostic_pipeline(self, ticket_data):
        # 1. Create report
        report = DiagnosticReport.objects.create(
            title=ticket_data["title"],
            description=ticket_data["description"],
            status="Pending"
        )

        # 2. Calculate severity
        severity = self.severity_agent.calculate(ticket_data)
        report.severity = severity
        report.save()

        # 3. Assign technician
        technician = self.assignment_agent.assign(report)

        report.assigned_technician = technician
        report.status = "Assigned"
        report.save()

        return report