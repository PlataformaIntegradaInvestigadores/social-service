from rest_framework import permissions
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.jobs.domain.entities.company import Company


class CompanyChoicesView(APIView):
    """Vista para obtener las opciones de formularios de empresa."""

    permission_classes = [permissions.AllowAny]  # Puede ser público

    def get(self, request):
        """Retorna las opciones disponibles para los formularios de empresa."""
        industries = [
            {"value": choice[0], "label": choice[1]}
            for choice in Company.INDUSTRY_CHOICES
        ]

        employee_counts = [
            {"value": choice[0], "label": choice[1]}
            for choice in [
                ("1-10", "1-10 empleados"),
                ("11-50", "11-50 empleados"),
                ("51-200", "51-200 empleados"),
                ("201-500", "201-500 empleados"),
                ("501-1000", "501-1000 empleados"),
                ("1000+", "Más de 1000 empleados"),
            ]
        ]

        return Response({"industries": industries, "employee_counts": employee_counts})
