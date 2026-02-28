from django.contrib import admin
from .models import DiagnosticReport, TechnicianReport
# Register your models here.
admin.site.register(DiagnosticReport)
admin.site.register(TechnicianReport)