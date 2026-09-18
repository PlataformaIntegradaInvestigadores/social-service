import logging
import random

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.apps import apps
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import generics, permissions, status, viewsets
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.concensus.domain.default_topics import DEFAULT_RECOMMENDED_TOPICS
from apps.concensus.domain.entities.final_topic_order import FinalTopicOrder
from apps.concensus.domain.entities.notification import NotificationPhaseOne
from apps.concensus.domain.entities.topic import RecommendedTopic, Topic, TopicAddedUser
from apps.concensus.infrastructure.api.v1.serializers.final_topic_serializer import (
    FinalTopicOrderSerializer,
)
from apps.concensus.infrastructure.api.v1.serializers.topic_serializer import (
    RecommendedTopicSerializer,
    TopicAddedUserSerializer,
    TopicSerializer,
)
from apps.concensus.infrastructure.external.grs_client import fetch_grs_topics
from apps.custom_auth.identity_principal import snapshot_from_principal
from apps.custom_auth.identity_profile_client import get_identity_group_detail

logger = logging.getLogger(__name__)


def _group_snapshot(group_id):
    return {"id": str(group_id)}


class TopicViewSet(viewsets.ModelViewSet):
    serializer_class = TopicSerializer
    queryset = Topic.objects.all()
    permission_classes = [permissions.AllowAny]

    @extend_schema(
        description="List of topics for a group",
        parameters=[
            OpenApiParameter(
                name="group_id",
                location=OpenApiParameter.QUERY,
                description="Group ID",
                required=True,
                type=str,
            )
        ],
    )
    def list(self, request, *args, **kwargs):
        group_id = request.query_params.get("group_id")
        topics = Topic.objects.filter(group_identity_id=str(group_id))
        serializer = TopicSerializer(topics, many=True).data
        return Response({"data": serializer}, status=status.HTTP_200_OK)


class RandomRecommendedTopicView(generics.ListAPIView):
    serializer_class = RecommendedTopicSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        group_id = self.kwargs.get("group_id")

        if group_id:
            already_assigned = RecommendedTopic.objects.filter(
                group_identity_id=str(group_id)
            ).order_by("id")

            if already_assigned.exists():
                return already_assigned

        grs_topics = self._get_grs_topics(group_id) if group_id else None

        if grs_topics:
            return grs_topics

        queryset = RecommendedTopic.objects.filter(group_identity_id__isnull=True)
        sampled_queryset = random.sample(list(queryset), min(len(queryset), 5))

        if group_id and len(sampled_queryset) < 5:
            sampled_queryset.extend(
                self._create_fallback_topics(
                    group_id,
                    excluded_names={topic.topic_name for topic in sampled_queryset},
                    count=5 - len(sampled_queryset),
                )
            )

        return sorted(sampled_queryset, key=lambda topic: topic.topic_name)

    @staticmethod
    def _create_fallback_topics(group_id, excluded_names, count):
        """Crea los tópicos que antes dependían de datos precargados en la BD."""
        candidates = [
            topic_name
            for topic_name in DEFAULT_RECOMMENDED_TOPICS
            if topic_name not in excluded_names
        ]
        selected_names = random.sample(candidates, min(len(candidates), count))

        return RecommendedTopic.objects.bulk_create(
            [
                RecommendedTopic(
                    topic_name=topic_name,
                    group_identity_id=str(group_id),
                    group_snapshot=_group_snapshot(group_id),
                )
                for topic_name in selected_names
            ]
        )

    def _get_grs_topics(self, group_id):
        """Si algún miembro del grupo (resuelto vía profile_identity_backend,
        fuente canónica de grupos) tiene un scopus_id vinculado a un grupo
        persistente del GRS, crea RecommendedTopic reales a partir de esas
        recomendaciones. Si no hay vínculo (o algún servicio no responde),
        retorna None para que get_queryset() use el muestreo aleatorio."""
        group_detail = get_identity_group_detail(
            group_id,
            authorization_header=self.request.headers.get("Authorization", ""),
        )
        if not group_detail:
            return None

        scopus_ids = [
            user.get("scopus_id")
            for user in group_detail.get("users", [])
            if user.get("scopus_id")
        ]
        if not scopus_ids:
            return None

        topic_names = fetch_grs_topics(scopus_ids, k=5)
        if not topic_names:
            return None

        return [
            RecommendedTopic.objects.create(
                topic_name=name,
                group_identity_id=str(group_id),
                group_snapshot=_group_snapshot(group_id),
            )
            for name in topic_names
        ]

    def list(self, request, *args, **kwargs):
        response = super().list(request, *args, **kwargs)
        group_id = self.kwargs.get("group_id")
        if group_id:
            for topic in response.data:
                RecommendedTopic.objects.filter(id=topic["id"]).update(
                    group_identity_id=str(group_id),
                    group_snapshot=_group_snapshot(group_id),
                )
        return response


class RecommendedTopicsByGroupView(generics.ListAPIView):
    serializer_class = RecommendedTopicSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        group_id = self.kwargs["group_id"]
        return RecommendedTopic.objects.filter(
            group_identity_id=str(group_id)
        ).order_by("topic_name")


class FinalTopicsVotedByUserView(generics.ListAPIView):
    serializer_class = FinalTopicOrderSerializer
    permission_classes = [permissions.IsAuthenticated]

    def list(self, request, *args, **kwargs):
        user = self.request.user
        group_id = self.kwargs["group_id"]

        final_topics = FinalTopicOrder.objects.filter(
            idGroup_identity_id=str(group_id),
            idUser_identity_id=str(user.id),
        ).order_by("-posFinal")
        final_topics_serializer = FinalTopicOrderSerializer(final_topics, many=True)

        results = []
        for topic in final_topics_serializer.data:
            topic_id = topic["idTopic"]
            topic_name = RecommendedTopic.objects.get(id=topic_id).topic_name
            labels = topic["label"]
            tags = (
                [tag.strip() for tag in labels.split(",")]
                if labels and "," in labels
                else ([labels] if labels else [])
            )
            results.append(
                {
                    "id": topic_id,
                    "topic_name": topic_name,
                    "posFinal": topic["posFinal"],
                    "tags": tags,
                }
            )

        return Response({"data": results})


class TopicsAddedByGroupView(generics.ListAPIView):
    serializer_class = TopicAddedUserSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        group_id = self.kwargs["group_id"]
        return TopicAddedUser.objects.filter(group_identity_id=str(group_id))


class GroupTopicsView(generics.ListAPIView):
    permission_classes = [permissions.IsAuthenticated]

    def list(self, request, *args, **kwargs):
        group_id = self.kwargs["group_id"]
        recommended_topics = RecommendedTopic.objects.filter(
            group_identity_id=str(group_id)
        )
        added_topics = TopicAddedUser.objects.filter(group_identity_id=str(group_id))

        return Response(
            {
                "recommended_topics": RecommendedTopicSerializer(
                    recommended_topics, many=True
                ).data,
                "added_topics": TopicAddedUserSerializer(added_topics, many=True).data,
            }
        )


class AddTopicView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, group_id):
        topic_name = request.data.get("topic")
        user_id = str(request.data.get("user_id") or request.user.id)

        if not topic_name or not user_id:
            return Response(
                {"error": "Invalid data"}, status=status.HTTP_400_BAD_REQUEST
            )

        UserPhase = apps.get_model("concensus", "UserPhase")
        users_in_phase_two_or_higher = UserPhase.objects.filter(
            group_identity_id=str(group_id),
            phase__gte=1,
        ).exists()
        if users_in_phase_two_or_higher:
            return Response(
                {
                    "error": "A user in this group is already in phase 2, "
                    "adding new topics is not allowed."
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        user_topic_count = TopicAddedUser.objects.filter(
            group_identity_id=str(group_id),
            user_identity_id=user_id,
        ).count()
        if user_topic_count > 0:
            return Response(
                {"error": "You can only add one topic per group"},
                status=status.HTTP_403_FORBIDDEN,
            )

        existing_recommended_topic = RecommendedTopic.objects.filter(
            topic_name=topic_name,
            group_identity_id=str(group_id),
        ).first()

        if existing_recommended_topic:
            existing_topic_added_user = TopicAddedUser.objects.filter(
                topic=existing_recommended_topic,
                group_identity_id=str(group_id),
            ).first()
            if existing_topic_added_user:
                return Response(
                    {"error": "Topic already exists in this group"},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            recommended_topic = existing_recommended_topic
        else:
            recommended_topic = RecommendedTopic.objects.create(
                topic_name=topic_name,
                group_identity_id=str(group_id),
                group_snapshot=_group_snapshot(group_id),
            )

        user_snapshot = snapshot_from_principal(request.user)
        group_snapshot = _group_snapshot(group_id)
        topic_added = TopicAddedUser.objects.create(
            topic=recommended_topic,
            group_identity_id=str(group_id),
            group_snapshot=group_snapshot,
            user_identity_id=user_id,
            user_snapshot=user_snapshot,
        )

        serializer = TopicAddedUserSerializer(topic_added)
        display_name = request.user.get_full_name() or request.user.username or user_id
        message = f"{display_name} added topic <i>{topic_name}</i>"
        NotificationPhaseOne.objects.create(
            user_identity_id=user_id,
            user_snapshot=user_snapshot,
            group_identity_id=str(group_id),
            group_snapshot=group_snapshot,
            notification_type="new_topic",
            message=message,
        )

        profile_picture_url = user_snapshot.get("profile_picture") or None
        channel_layer = get_channel_layer()
        async_to_sync(channel_layer.group_send)(
            f"group_{group_id}",
            {
                "type": "group_message",
                "message": {
                    "type": "new_topic",
                    "id": topic_added.id,
                    "topic_name": topic_added.topic.topic_name,
                    "user_id": topic_added.user_identity_id,
                    "group_id": topic_added.group_identity_id,
                    "added_at": topic_added.added_at.isoformat(),
                    "notification_message": message,
                    "profile_picture_url": profile_picture_url,
                },
            },
        )

        return Response(serializer.data, status=status.HTTP_201_CREATED)
