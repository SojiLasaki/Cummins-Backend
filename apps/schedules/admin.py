from django.contrib import admin
from .models import Schedule


@admin.register(Schedule)
class ScheduleAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "technician",
        "customer",
        "ticket",
        "scheduled_time",
        "duration",
        "ended_at",
        "is_active",
    )
    list_filter = ("technician", "customer", "ticket", "ended_at")
    search_fields = (
        "technician__profile__user__username",
        "customer__user__username",
        "ticket__ticket_id",
    )
    readonly_fields = ("created_at", "updated_at")
