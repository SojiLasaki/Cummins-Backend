from django.shortcuts import render
from rest_framework import viewsets
from .models import TechnicianProfile
from .serializers import TechnicianProfileSerializer
from rest_framework.decorators import api_view
from rest_framework.response import Response
from apps.manuals.models import Manual
from apps.manuals.serializers import ManualSerializer
from apps.inventory.models import Part
from apps.inventory.serializers import PartSerializer
from apps.inventory.models import Component
from apps.inventory.serializers import ComponentSerializer
from apps.diagnostics.models import DiagnosticReport
from apps.diagnostics.serializers import DiagnosticReportSerializer
# Create your views here.

class TechnicianProfileViewSet(viewsets.ModelViewSet):
    queryset = TechnicianProfile.objects.all()
    serializer_class = TechnicianProfileSerializer
    lookup_field = "id"


@api_view(["GET"])
def technician_search(request):
    query = request.GET.get("q", "")

    manuals = Manual.objects.filter(title__icontains=query)
    parts = Part.objects.filter(name__icontains=query)
    components = Component.objects.filter(name__icontains=query)
    diagnostics = DiagnosticReport.objects.filter(title__icontains=query)

    return Response({
        "manuals": ManualSerializer(manuals, many=True).data,
        "parts": PartSerializer(parts, many=True).data,
        "components": ComponentSerializer(components, many=True).data,
        "diagnostics": DiagnosticReportSerializer(diagnostics, many=True).data,
    })