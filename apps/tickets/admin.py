from django.contrib import admin
from apps.agents.assignment_engine import assign_best_technician
from django.utils import timezone
from .models import *

# Register your models here.
admin.site.register(Ticket)
# class TicketAdmin(admin.ModelAdmin):
#     list_display = ('ticket_id', 'title', 'created_by', 'assigned_technician', 'status')
#     readonly_fields = ('created_by',)

# class TicketAdmin(admin.ModelAdmin):
#     list_display = ('ticket_id', 'title', 'created_by', 'assigned_technician', 'status')
#     readonly_fields = ('created_by', 'assigned_technician', 'assigned_at', 'auto_assigned')

    # def save_model(self, request, obj, form, change):
    #     # Only set these fields when creating a new object
    #     if not obj.pk:
    #         # obj.created_by = request.user
            
    #         # Auto-assign technician using your assignment engine
    #         technician = assign_best_technician(obj)
    #         if technician:
    #             obj.assigned_technician = technician
    #             obj.auto_assigned = True
    #             obj.assigned_at = timezone.now()
        
        # super().save_model(request, obj, form, change)