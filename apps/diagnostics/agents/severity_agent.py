class SeverityAgent:

    def calculate(self, ticket_data):
        # Replace with your numeric scoring system
        if "engine failure" in ticket_data["description"].lower():
            return 5
        if "warning" in ticket_data["description"].lower():
            return 3
        return 1