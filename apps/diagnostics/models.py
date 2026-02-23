from django.db import models
from apps.customers.models import CustomerProfile
from apps.inventory.models import Component, Part
from apps.technicians.models import TechnicianProfile
# from apps.tickets.models import Ticket
# from apps.tickets.models import Ticket
import uuid

class DiagnosticReport(models.Model):
    LEVEL = (
        ('Junior', 'Junior'),
        ('Mid', 'Mid'),
        ('Senior', 'Senior'),
    )
    POSITION_CHOICES = (
        ("Engine", "Engine_Technician"),
        ("Electrical", "Electrical_Technician"),
    )
    SEVERITY = (
        ("Low", "Low"),
        ("Medium", "Medium"),
        ("Critical", "Critical"),
    )
    STATUS = (
        ("Pending", "Pending"),
        ("In_Progress", "In Progress"),
        ("Resolved", "Resolved"),
        ("Failed", "Failed"),
    )
    diagnostics_id = models.CharField(max_length=190, unique=True,  null=True, blank=True)
    # ticket_id = models.ForeignKey(Ticket, on_delete=models.SET_NULL, null=True, blank=True)
    title = models.CharField(max_length=200, null=True, blank=True)
    severity = models.CharField(max_length=20, choices=SEVERITY, default="Low")
    status = models.CharField(max_length=20, choices=STATUS, default="Pending")
    # ticket = models.ForeignKey(Ticket, on_delete=models.CASCADE)
    specialization = models.CharField(max_length=50, choices=POSITION_CHOICES, default="Engine")
    expertise_requirement = models.CharField(max_length=50, choices=LEVEL, default="Junior")
    assigned_technician = models.ForeignKey(TechnicianProfile, on_delete=models.SET_NULL, null=True, blank=True)
    fault_code = models.CharField(max_length=100, null=True, blank=True)
    # customer = models.ForeignKey("users.User", on_delete=models.CASCADE, null=True, blank=True, related_name="diagnostic_reports")
    customer = models.ForeignKey(CustomerProfile, on_delete=models.CASCADE, null=True, blank=True, related_name="diagnostic_reports")
    component = models.ForeignKey(Component, on_delete=models.SET_NULL, null=True, blank=True, related_name="diagnostic_reports")
    part = models.ManyToManyField(Part, related_name="diagnostic_reports")
    ai_summary = models.TextField()
    probable_cause = models.TextField()
    description = models.TextField(null=True, blank=True)
    recommended_actions = models.TextField()
    confidence_score = models.FloatField()
    identified_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    resolved_at = models.DateTimeField(null=True, blank=True)

    # AI agent - change to model
    performed_by = models.CharField(max_length=100, null=True, blank=True)
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    def __str__(self):
        customer_name = self.customer.user.username if self.customer else "Unknown"
        component_name = self.component.name if self.component else "Unknown Component"
        return f"Customer {customer_name or '' } - Component: {component_name} - Specializaton {self.specialization} - Expertise: {self.expertise_requirement}"
    
    class Meta:
        verbose_name = "Diagnostic Report"
        verbose_name_plural = "Diagnostic Reports"