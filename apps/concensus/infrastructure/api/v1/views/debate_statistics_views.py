from django.core.cache import cache
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.concensus.domain.entities.debate_participant_posture import UserPosture


class StatisticsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, debate_id):
        total_agree = UserPosture.objects.filter(
            debate_id=debate_id, posture="agree"
        ).count()
        total_disagree = UserPosture.objects.filter(
            debate_id=debate_id, posture="disagree"
        ).count()
        total_neutral = UserPosture.objects.filter(
            debate_id=debate_id, posture="neutral"
        ).count()

        # Obtener usuarios únicos conectados desde Redis
        connected_users = cache.get(f"chat_users_{debate_id}", set())
        total_active_users = len(connected_users)

        data = {
            "debate_id": debate_id,
            "total_agree": total_agree,
            "total_disagree": total_disagree,
            "total_neutral": total_neutral,
            "total_active_users": total_active_users,
        }
        return Response(data)
