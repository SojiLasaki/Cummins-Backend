# apps/agents/system_orchestrator.py

from diagnostic_agent import DiagnosticAgent
from ticketing_agent import TicketingAgent
from assignment_engine import AssignmentAgent
from order_agent import OrderAgent


class SystemOrchestrator:

    def run_full_diagnostic_pipeline(self, data):

        diagnostic_agent = DiagnosticAgent()
        report = diagnostic_agent.run(data)

        ticket_agent = TicketAgent()
        ticket = ticket_agent.create_ticket(report)

        assignment_agent = AssignmentAgent()
        assignment_agent.assign(ticket)

        order_agent = OrderAgent()
        order_agent.process(ticket)

        return ticket