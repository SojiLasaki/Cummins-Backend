from django.db import models
from apps.agents.diagnostic_agent import DiagnosticAgent
from apps.agents.ticketing_agent import TicketingAgent
from apps.agents.assignment_engine import AssignmentEngine
# Create your models here.
class SystemOrchestrator:

    def run_full_diagnostic_pipeline(self, vehicle_data):
        # 1. AI scan
        report = DiagnosticAgent().scan(vehicle_data)

        # 2. Create ticket
        ticket = TicketingAgent().create_ticket(report)

        # 3. Assign technician
        AssignmentEngine().assign(ticket)

        # 4. Check inventory / reorder
        OrderAgent().handle_parts(ticket)

        return ticket