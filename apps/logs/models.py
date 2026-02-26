import uuid
from django.db import models
from django.conf import settings



class AgentExecutionLog(models.Model):
    agent_name = models.CharField(max_length=100)
    status = models.CharField(max_length=50)
    started_at = models.DateTimeField()
    finished_at = models.DateTimeField(null=True, blank=True)
    metadata = models.JSONField()

class ActivityLog(models.Model):

    EVENT_TYPES = (
        ("user_action", "User Action"),
        ("agent_action", "AI Agent Action"),
        ("system_event", "System Event"),
        ("security_event", "Security Event"),
    )

    SEVERITY_LEVELS = (
        ("info", "Info"),
        ("warning", "Warning"),
        ("error", "Error"),
        ("critical", "Critical"),
    )

    STATUS_CHOICES = (
        ("success", "Success"),
        ("failed", "Failed"),
        ("pending", "Pending"),
        ("escalated", "Escalated"),
    )
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="activity_logs")
    event_type = models.CharField(max_length=50, choices=EVENT_TYPES)
    agent_name = models.CharField(max_length=100, blank=True, null=True)
    action = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    object_type = models.CharField(max_length=100, blank=True, null=True)
    object_id = models.UUIDField(blank=True, null=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="success")
    severity = models.CharField(max_length=20, choices=SEVERITY_LEVELS, default="info")
    ip_address = models.GenericIPAddressField(blank=True, null=True)
    user_agent = models.TextField(blank=True, null=True)
    metadata = models.JSONField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user"]),
            models.Index(fields=["event_type"]),
            models.Index(fields=["severity"]),
            models.Index(fields=["created_at"]),
        ]

    def __str__(self):
        return f"{self.user} - {self.action} - {self.status}"