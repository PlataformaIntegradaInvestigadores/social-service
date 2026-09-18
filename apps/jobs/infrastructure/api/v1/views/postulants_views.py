from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.jobs.domain.entities.jobs import Jobs
from apps.jobs.domain.entities.postulants import Postulants
from apps.jobs.infrastructure.api.v1.serializers.postulants_serializer import (
    PostulantsSerializer,
)


class PostulantsView(APIView):
    permission_classes = [IsAuthenticated]

    def get_object(self, pk):
        try:
            return Postulants.objects.get(pk=pk)
        except Postulants.DoesNotExist:
            return None

    def get_queryset(self):
        """
        Filtra las postulaciones según el tipo de usuario
        """
        user = self.request.user
        if hasattr(user, "company_name"):  # Es una compañía
            # La compañía ve todas las postulaciones a sus trabajos
            return Postulants.objects.filter(job__company=user)
        else:  # Es un usuario normal
            # El usuario solo ve sus propias postulaciones
            return Postulants.objects.filter(user_identity_id=str(user.id))

    def get(self, request, pk=None):
        if pk:
            postulant = self.get_object(pk)
            if not postulant:
                return Response(
                    {"error": "Postulación no encontrada"},
                    status=status.HTTP_404_NOT_FOUND,
                )

            # Verificar permisos
            user = request.user
            if hasattr(user, "company_name"):
                # Las compañías solo ven postulaciones a sus trabajos
                if postulant.job.company != user:
                    return Response(
                        {"error": "No tienes permisos para ver esta postulación"},
                        status=status.HTTP_403_FORBIDDEN,
                    )
            else:
                # Los usuarios solo ven sus propias postulaciones
                if postulant.user_identity_id != str(user.id):
                    return Response(
                        {"error": "No tienes permisos para ver esta postulación"},
                        status=status.HTTP_403_FORBIDDEN,
                    )

            serializer = PostulantsSerializer(postulant)
            return Response(serializer.data)
        else:
            # Aplicar filtros
            queryset = self.get_queryset()
            job_id = request.GET.get("job_id", "")
            status_filter = request.GET.get("status", "")

            if job_id:
                queryset = queryset.filter(job_id=job_id)
            if status_filter:
                queryset = queryset.filter(status=status_filter)

            serializer = PostulantsSerializer(queryset, many=True)
            return Response(serializer.data)

    def post(self, request):
        # Solo los usuarios normales pueden postularse
        if hasattr(request.user, "company_name"):
            return Response(
                {"error": "Las compañías no pueden postularse a trabajos"},
                status=status.HTTP_403_FORBIDDEN,
            )

        job_id = request.data.get("job")
        if not job_id:
            return Response(
                {"error": "ID del trabajo es requerido"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            job = Jobs.objects.get(id=job_id)
        except Jobs.DoesNotExist:
            return Response(
                {"error": "Trabajo no encontrado"}, status=status.HTTP_404_NOT_FOUND
            )

        # Verificar si ya se postuló
        if Postulants.objects.filter(
            user_identity_id=str(request.user.id), job=job
        ).exists():
            return Response(
                {"error": "Ya te has postulado a este trabajo"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        # Crear los datos para el serializer sin incluir job en los datos de validación
        serializer_data = request.data.copy()
        if "job" in serializer_data:
            del serializer_data["job"]

        serializer = PostulantsSerializer(
            data=serializer_data, context={"request": request}
        )
        if serializer.is_valid():
            serializer.save(user=request.user, job=job)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def put(self, request, pk):
        postulant = self.get_object(pk)
        if not postulant:
            return Response(
                {"error": "Postulación no encontrada"}, status=status.HTTP_404_NOT_FOUND
            )

        user = request.user
        update_data = request.data
        # Solo las compañías pueden actualizar el estado de las postulaciones
        if hasattr(user, "company_name"):
            if postulant.job.company != user:
                return Response(
                    {"error": "No tienes permisos para actualizar esta postulación"},
                    status=status.HTTP_403_FORBIDDEN,
                )
        else:
            # Los usuarios solo pueden actualizar su carta de presentación
            if postulant.user_identity_id != str(user.id):
                return Response(
                    {"error": "No tienes permisos para actualizar esta postulación"},
                    status=status.HTTP_403_FORBIDDEN,
                )
            # Limitar campos que pueden actualizar
            allowed_fields = ["cover_letter", "resume_file"]
            update_data = {
                k: v for k, v in request.data.items() if k in allowed_fields
            }

        serializer = PostulantsSerializer(postulant, data=update_data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, pk):
        postulant = self.get_object(pk)
        if not postulant:
            return Response(
                {"error": "Postulación no encontrada"}, status=status.HTTP_404_NOT_FOUND
            )

        # Solo el usuario que se postuló puede eliminar su postulación
        if hasattr(request.user, "company_name") or postulant.user_identity_id != str(
            request.user.id
        ):
            return Response(
                {"error": "No tienes permisos para eliminar esta postulación"},
                status=status.HTTP_403_FORBIDDEN,
            )

        postulant.delete()
        return Response(
            {"message": "Postulación eliminada exitosamente"},
            status=status.HTTP_204_NO_CONTENT,
        )


class ApplicationStatusView(APIView):
    """Vista para verificar el estado de postulación de un usuario
    a un trabajo específico"""

    permission_classes = [IsAuthenticated]

    def get(self, request, job_id):
        """
        Verificar si el usuario actual ya postuló al trabajo especificado
        """
        # Solo usuarios regulares pueden verificar su estado de postulación
        if hasattr(request.user, "company_name"):
            return Response(
                {"error": "Las compañías no pueden verificar estado de postulación"},
                status=status.HTTP_403_FORBIDDEN,
            )

        try:
            job = Jobs.objects.get(id=job_id)
        except Jobs.DoesNotExist:
            return Response(
                {"error": "Trabajo no encontrado"}, status=status.HTTP_404_NOT_FOUND
            )

        try:
            application = Postulants.objects.get(
                user_identity_id=str(request.user.id), job=job
            )
            return Response(
                {
                    "has_applied": True,
                    "application": {
                        "id": application.id,
                        "status": application.status,
                        "status_display": application.get_status_display_name(),
                        "applied_at": application.applied_at,
                        "updated_at": application.updated_at,
                    },
                }
            )
        except Postulants.DoesNotExist:
            return Response({"has_applied": False, "application": None})


class CompanyApplicationsView(APIView):
    """Vista específica para que las compañías gestionen las
    postulaciones a sus trabajos"""

    permission_classes = [IsAuthenticated]

    def get(self, request, job_id=None):
        """
        Obtener postulaciones a los trabajos de la compañía
        Si se proporciona job_id, filtra por ese trabajo específico
        """
        # Solo las compañías pueden acceder a esta vista
        if not hasattr(request.user, "company_name"):
            return Response(
                {"error": "Solo las compañías pueden acceder a esta vista"},
                status=status.HTTP_403_FORBIDDEN,
            )

        # Filtros opcionales
        status_filter = request.GET.get("status", "")

        # Obtener todas las postulaciones a trabajos de la compañía
        queryset = Postulants.objects.filter(job__company=request.user).select_related(
            "job"
        )

        # Si se especifica un job_id, filtrar por ese trabajo
        if job_id:
            queryset = queryset.filter(job_id=job_id)

        if status_filter:
            queryset = queryset.filter(status=status_filter)

        serializer = PostulantsSerializer(queryset, many=True)
        return Response(serializer.data)

    def put(self, request, job_id=None):
        """
        Actualizar el estado de múltiples postulaciones
        """
        # Solo las compañías pueden acceder a esta vista
        if not hasattr(request.user, "company_name"):
            return Response(
                {"error": "Solo las compañías pueden acceder a esta vista"},
                status=status.HTTP_403_FORBIDDEN,
            )

        application_id = request.data.get("application_id")
        new_status = request.data.get("status")
        notes = request.data.get("notes", "")

        if not application_id or not new_status:
            return Response(
                {"error": "application_id y status son requeridos"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            application = Postulants.objects.get(
                id=application_id, job__company=request.user
            )

            application.status = new_status
            if notes:
                application.notes = notes
            application.save()

            serializer = PostulantsSerializer(application)
            return Response(serializer.data)

        except Postulants.DoesNotExist:
            return Response(
                {"error": "Postulación no encontrada"}, status=status.HTTP_404_NOT_FOUND
            )


class UserApplicationsView(APIView):
    """Vista específica para que los usuarios vean sus propias postulaciones"""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        """
        Obtener todas las postulaciones del usuario actual
        """
        # Solo usuarios regulares pueden acceder a esta vista
        if hasattr(request.user, "company_name"):
            return Response(
                {"error": "Las compañías no pueden acceder a esta vista"},
                status=status.HTTP_403_FORBIDDEN,
            )

        # Filtros opcionales
        status_filter = request.GET.get("status", "")

        # Obtener todas las postulaciones del usuario
        queryset = Postulants.objects.filter(
            user_identity_id=str(request.user.id)
        ).select_related("job", "job__company")

        if status_filter:
            queryset = queryset.filter(status=status_filter)

        serializer = PostulantsSerializer(queryset, many=True)
        return Response(serializer.data)
