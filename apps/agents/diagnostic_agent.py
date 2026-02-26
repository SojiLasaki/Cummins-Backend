# apps/ai/diagnostic_agent.py

class DiagnosticAgent:

    def run_scan(self, machine_data):
        # Step 1: AI logic / ML model call / rules engine
        report = self.analyze(machine_data)

        # Step 2: Trigger ticket agent
        from apps.agents.ticketing_agent import TicketingAgent
        TicketingAgent().create_ticket_from_report(report)

        return report

    def analyze(self, data):
        # Replace with real AI model later
        return {
            "title": "Fuel pressure imbalance",
            "fault_code": "FP-4021",
            "specialization": "engine",
            "severity": "high",
            "description": "Irregular fuel pressure detected.",
            "recommended_part": "Fuel Injector 6.7L"
        }