from django.contrib import admin

from apps.tickets.models import Ticket, TicketResolutionPattern


@admin.register(Ticket)
class TicketAdmin(admin.ModelAdmin):
    list_display = ("ticket_id", "title", "status", "priority", "specialization", "assigned_technician", "created_at")
    list_filter = ("status", "specialization", "priority")
    search_fields = ("ticket_id", "title", "description", "issue_description")
    readonly_fields = ("created_at", "assigned_at", "resolved_at", "closed_at")


@admin.register(TicketResolutionPattern)
class TicketResolutionPatternAdmin(admin.ModelAdmin):
    list_display = ("signature_hash", "specialization", "component_name", "fault_code", "success_count", "updated_at")
    list_filter = ("specialization",)
    search_fields = ("signature_hash", "component_name", "fault_code", "issue_text")
    readonly_fields = ("created_at", "updated_at")
