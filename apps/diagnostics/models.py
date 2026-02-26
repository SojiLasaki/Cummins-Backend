from django.db import models
from apps.customers.models import CustomerProfile
from apps.inventory.models import Component, Part
from apps.tickets.models import Ticket
import uuid


class DiagnosticReport(models.Model):

    LEVEL = (
        ('junior', 'Junior'),
        ('mid', 'Mid'),
        ('senior', 'Senior'),
    )
    POSITION_CHOICES = (
        ("engine", "Engine Technician"),
        ("electrical", "Electrical Technician"),
    )
    SEVERITY = (
        (1, "Low"),
        (2, "Medium"),
        (3, "High"),
        (4, "Severe"),
    )
    STATUS = (
        ("pending", "Pending"),
        ("in_progress", "In Progress"),
        ("resolved", "Resolved"),
        ("failed", "Failed"),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    diagnostics_id = models.CharField(max_length=190, unique=True, null=True, blank=True)
    ticket_id = models.ForeignKey(
        Ticket,
        on_delete=models.CASCADE,
        related_name="diagnostic_reports",
        blank=True,
        null=True
    )
    title = models.CharField(max_length=200, blank=True, null=True)
    severity = models.CharField(max_length=20, choices=SEVERITY, default=2)
    status = models.CharField(max_length=20, choices=STATUS, default="pending")
    specialization = models.CharField(max_length=50, choices=POSITION_CHOICES, default="engine")
    expertise_requirement = models.CharField(max_length=50, choices=LEVEL, default="junior")
    customer = models.ForeignKey(CustomerProfile, on_delete=models.SET_NULL, null=True, blank=True, related_name="diagnostic_reports")
    assigned_technician = models.ForeignKey(
        "technicians.TechnicianProfile",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="diagnostic_reports"
    )
    fault_code = models.CharField(max_length=100, blank=True, null=True)
    component = models.ForeignKey(
        Component,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="diagnostic_reports"
    )
    parts = models.ManyToManyField(
        Part,
        blank=True,
        related_name="diagnostic_reports"
    )
    ai_summary = models.TextField(blank=True, null=True)
    probable_cause = models.TextField(blank=True, null=True)
    description = models.TextField(blank=True, null=True)
    recommended_actions = models.TextField(blank=True, null=True)
    confidence_score = models.FloatField(null=True, blank=True)
    identified_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    requires_follow_up = models.BooleanField(default=False)
    repeat_issue = models.BooleanField(default=False)
    diagnostic_duration_minutes = models.IntegerField(null=True, blank=True)
    performed_by = models.CharField(max_length=100, blank=True, null=True)

    def __str__(self):
        return f"{self.ticket_id} - {self.specialization} - {self.expertise_requirement}"

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Diagnostic Report"
        verbose_name_plural = "Diagnostic Reports"



class TechnicianReport(models.Model):
    ticket = models.ForeignKey(
        "tickets.Ticket",
        on_delete=models.CASCADE,
        related_name="technician_reports"
    )

    technician = models.ForeignKey(
        'technicians.TechnicianProfile',
        on_delete=models.CASCADE
    )

    findings = models.TextField()
    actions_taken = models.TextField()
    parts_used = models.ManyToManyField("inventory.Part", blank=True)
    report_id = models.CharField(max_length=190, unique=True, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Technician Report"
        verbose_name_plural = "Technician Reports"
