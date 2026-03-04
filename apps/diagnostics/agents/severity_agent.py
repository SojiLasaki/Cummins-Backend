class SeverityAgent:

    def calculate(self, ticket_data):
        """
        Return an int severity compatible with model choices:
        1=Low, 2=Medium, 3=High, 4=Severe.
        """
        description = (ticket_data.get("description") or "").lower()
        title = (ticket_data.get("title") or "").lower()
        text = f"{title} {description}"

        if "engine failure" in text or "critical" in text or "shutdown" in text:
            return 4
        if "high" in text or "overheat" in text or "leak" in text:
            return 3
        if "warning" in text or "degraded" in text:
            return 2
        return 1