from rest_framework import serializers
from .models import DiagnosticReport

class DiagnosticReportSerializer(serializers.ModelSerializer):
    class Meta:
        model = DiagnosticReport
        fields = '__all__'