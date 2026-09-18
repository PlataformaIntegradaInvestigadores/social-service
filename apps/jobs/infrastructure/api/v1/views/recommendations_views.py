import logging

from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.jobs.domain.services.jobs_service import JobsService
from apps.jobs.infrastructure.api.v1.serializers.jobs_serializer import JobsSerializer

logger = logging.getLogger(__name__)


class JobRecommendationsView(APIView):
    """
    Obtiene recomendaciones personalizadas de trabajos basadas en el perfil del usuario
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            limit = int(request.GET.get("limit", 10))
            limit = min(limit, 50)  # Máximo 50 recomendaciones
        except (ValueError, TypeError):
            limit = 10

        jobs_service = JobsService()
        recommendations = jobs_service.get_personalized_job_recommendations(
            user=request.user, limit=limit
        )

        serializer = JobsSerializer(
            recommendations, many=True, context={"request": request}
        )
        return Response({"count": len(recommendations), "results": serializer.data})


class JobTrendingView(APIView):
    """
    Obtiene trabajos trending basados en interacciones, visualizaciones
    y aplicaciones recientes
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            limit = int(request.GET.get("limit", 10))
            limit = min(limit, 50)  # Máximo 50 trabajos trending
        except (ValueError, TypeError):
            limit = 10

        jobs_service = JobsService()
        trending_jobs = jobs_service.get_trending_jobs(limit=limit)

        serializer = JobsSerializer(
            trending_jobs, many=True, context={"request": request}
        )
        return Response({"count": len(trending_jobs), "results": serializer.data})


class JobSemanticSearchView(APIView):
    """
    Búsqueda semántica de trabajos usando embeddings y filtros avanzados
    """

    permission_classes = [IsAuthenticated]

    def post(self, request):
        query = request.data.get("query", "")
        limit = request.data.get("limit", 10)
        filters = request.data.get("filters", {})

        if not query:
            return Response(
                {"error": "Query is required"}, status=status.HTTP_400_BAD_REQUEST
            )

        try:
            limit = min(int(limit), 50)  # Máximo 50 resultados
        except (ValueError, TypeError):
            limit = 10

        jobs_service = JobsService()
        search_results = jobs_service.semantic_search_jobs(
            query=query, filters=filters, limit=limit, user=request.user
        )

        serializer = JobsSerializer(
            search_results, many=True, context={"request": request}
        )
        return Response(
            {
                "query": query,
                "filters": filters,
                "count": len(search_results),
                "results": serializer.data,
            }
        )
