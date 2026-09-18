from django.db.models import Q
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.jobs.domain.entities.jobs import Jobs
from apps.jobs.infrastructure.api.v1.serializers.jobs_serializer import JobsSerializer


class JobsView(APIView):
    permission_classes = [IsAuthenticated]

    def get_object(self, pk):
        try:
            return Jobs.objects.get(pk=pk)
        except Jobs.DoesNotExist:
            return None

    def get_queryset(self):
        """
        Filtra los trabajos según el tipo de usuario
        """
        user = self.request.user
        if hasattr(user, "company_name"):  # Es una compañía
            return Jobs.objects.filter(company=user)
        else:  # Es un usuario normal, ve todos los trabajos
            return Jobs.objects.all()

    def get(self, request, pk=None):
        if pk:
            job = self.get_object(pk)
            if not job:
                return Response(
                    {"error": "Trabajo no encontrado"}, status=status.HTTP_404_NOT_FOUND
                )

            # Verificar permisos: compañías solo ven sus trabajos
            if hasattr(request.user, "company_name") and job.company != request.user:
                return Response(
                    {"error": "No tienes permisos para ver este trabajo"},
                    status=status.HTTP_403_FORBIDDEN,
                )

            serializer = JobsSerializer(job, context={"request": request})
            return Response(serializer.data)
        else:
            # Aplicar filtros de búsqueda
            queryset = self.get_queryset()
            query = request.GET.get("q", "")
            location = request.GET.get("location", "")
            job_type = request.GET.get("type", "")
            experience = request.GET.get("experience", "")
            remote = request.GET.get("remote", "")

            if query:
                queryset = queryset.filter(
                    Q(title__icontains=query)
                    | Q(description__icontains=query)
                    | Q(company__company_name__icontains=query)
                )

            if location:
                queryset = queryset.filter(location__icontains=location)

            if job_type:
                queryset = queryset.filter(job_type=job_type)

            if experience:
                queryset = queryset.filter(experience_level=experience)

            if remote:
                queryset = queryset.filter(is_remote=remote.lower() == "true")

            # Usar el serializer adecuado según si es listado o detalle
            # Para listados usar el serializer apropiado según el tipo de usuario
            user = request.user
            if hasattr(user, "company_name"):  # Es una compañía
                from apps.jobs.infrastructure.api.v1.serializers.jobs_serializer import (
                    JobsCompanySerializer,
                )

                serializer = JobsCompanySerializer(
                    queryset, many=True, context={"request": request}
                )
            else:  # Es un usuario normal
                from apps.jobs.infrastructure.api.v1.serializers.jobs_serializer import (
                    JobsListSerializer,
                )

                serializer = JobsListSerializer(
                    queryset, many=True, context={"request": request}
                )
            return Response(serializer.data)

    def post(self, request):
        # Solo las compañías pueden crear trabajos
        if not hasattr(request.user, "company_name"):
            return Response(
                {"error": "Solo las compañías pueden crear trabajos"},
                status=status.HTTP_403_FORBIDDEN,
            )

        # Crear una copia de los datos para no modificar el request original
        data = request.data.copy()

        # Remover el campo company si está presente, ya que se establece automáticamente
        if "company" in data:
            data.pop("company")

        serializer = JobsSerializer(data=data)
        if serializer.is_valid():
            serializer.save(company=request.user)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def put(self, request, pk):
        job = self.get_object(pk)
        if not job:
            return Response(
                {"error": "Trabajo no encontrado"}, status=status.HTTP_404_NOT_FOUND
            )

        # Solo la compañía propietaria puede editar
        if not hasattr(request.user, "company_name") or job.company != request.user:
            return Response(
                {"error": "No tienes permisos para editar este trabajo"},
                status=status.HTTP_403_FORBIDDEN,
            )

        serializer = JobsSerializer(job, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, pk):
        job = self.get_object(pk)
        if not job:
            return Response(
                {"error": "Trabajo no encontrado"}, status=status.HTTP_404_NOT_FOUND
            )

        # Solo la compañía propietaria puede eliminar
        if not hasattr(request.user, "company_name") or job.company != request.user:
            return Response(
                {"error": "No tienes permisos para eliminar este trabajo"},
                status=status.HTTP_403_FORBIDDEN,
            )

        job.delete()
        return Response(
            {"message": "Trabajo eliminado exitosamente"},
            status=status.HTTP_204_NO_CONTENT,
        )
