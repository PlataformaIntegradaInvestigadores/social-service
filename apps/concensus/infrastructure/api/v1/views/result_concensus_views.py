import logging
from collections import defaultdict

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.apps import apps
from rest_framework import generics, permissions, status
from rest_framework.response import Response

from apps.concensus.domain.entities.result_concensus import ConsensusResult

logger = logging.getLogger(__name__)


def get_user_data(group_id):
    RecommendedTopic = apps.get_model("concensus", "RecommendedTopic")
    FinalTopicOrder = apps.get_model("concensus", "FinalTopicOrder")
    UserExpertise = apps.get_model("concensus", "UserExpertise")
    UserPhase = apps.get_model("concensus", "UserPhase")

    completed_users = list(
        UserPhase.objects.filter(
            group_identity_id=str(group_id),
            phase__gte=2,
        ).values_list("user_identity_id", flat=True)
    )

    if not completed_users:
        raise ValueError("No users have completed phase 1 and 2")

    topics = RecommendedTopic.objects.filter(group_identity_id=str(group_id)).order_by(
        "topic_name"
    )
    topic_names = [topic.topic_name for topic in topics]
    positions_data = {topic_name: {} for topic_name in topic_names}
    expertise_data = {topic_name: {} for topic_name in topic_names}
    labels_data = {topic_name: [] for topic_name in topic_names}

    for user_id in completed_users:
        user_positions = FinalTopicOrder.objects.filter(
            idUser_identity_id=str(user_id),
            idGroup_identity_id=str(group_id),
        )
        user_expertise = UserExpertise.objects.filter(
            user_identity_id=str(user_id),
            group_identity_id=str(group_id),
        )

        for pos in user_positions:
            topic_name = pos.idTopic.topic_name
            positions_data[topic_name][str(user_id)] = pos.posFinal
            if pos.label:
                labels_data[topic_name].append(f"{user_id} rated it as {pos.label}")

        for exp in user_expertise:
            topic_name = exp.topic.topic_name
            expertise_data[topic_name][str(user_id)] = exp.expertise_level

    for topic_name in topic_names:
        for user_id in completed_users:
            expertise_data[topic_name].setdefault(str(user_id), 1)

    return (
        topics,
        topic_names,
        completed_users,
        positions_data,
        expertise_data,
        labels_data,
    )


class VotingAlgorithms:
    @staticmethod
    def schulze_voting_algorithm(
        positions_data: dict[str, dict[str, int]], topic_names: list[str]
    ) -> list[tuple]:
        p_matrix = defaultdict(lambda: defaultdict(int))
        for topic_name in topic_names:
            for other_topic_name in topic_names:
                if topic_name == other_topic_name:
                    continue
                for user, pos in positions_data[topic_name].items():
                    other_pos = positions_data[other_topic_name].get(
                        user, float("-inf")
                    )
                    if pos > other_pos:
                        p_matrix[topic_name][other_topic_name] += 1
                    elif pos < other_pos:
                        p_matrix[other_topic_name][topic_name] += 1

        strengths = defaultdict(lambda: defaultdict(int))
        for i in topic_names:
            for j in topic_names:
                if i != j:
                    strengths[i][j] = (
                        p_matrix[i][j] if p_matrix[i][j] > p_matrix[j][i] else 0
                    )

        for k in topic_names:
            for i in topic_names:
                for j in topic_names:
                    if i != j and i != k and j != k:
                        strengths[i][j] = max(
                            strengths[i][j], min(strengths[i][k], strengths[k][j])
                        )

        topic_strength = [
            (
                topic_name,
                sum(
                    1
                    for other_topic in topic_names
                    if strengths[topic_name][other_topic]
                    > strengths[other_topic][topic_name]
                ),
            )
            for topic_name in topic_names
        ]
        return sorted(topic_strength, key=lambda x: x[1], reverse=True)

    @staticmethod
    def calculate_positional_voting(
        topic_names: list[str],
        user_ids: list[str],
        positions_data: dict[str, dict[str, int]],
        expertise_data: dict[str, dict[str, int]],
    ) -> list[tuple]:
        weighted_rankings = {}
        for topic_name in topic_names:
            total_weighted_score = 0
            total_expertise = 0
            for user_id in user_ids:
                pos = positions_data[topic_name].get(str(user_id), 0)
                exp = expertise_data[topic_name].get(str(user_id), 1)
                total_weighted_score += pos * exp
                total_expertise += exp
            weighted_rankings[topic_name] = (
                total_weighted_score / total_expertise if total_expertise > 0 else 0
            )
        return sorted(weighted_rankings.items(), key=lambda x: x[1], reverse=True)


class ExecuteConsensusCalculationsView(generics.GenericAPIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, group_id):
        return _execute_consensus(
            group_id, voting_type="positional-voting", persist=True
        )


class ConsensusCalculationByVotingTypeView(generics.GenericAPIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, group_id, voting_type):
        if voting_type not in ["positional-voting", "non-positional-voting"]:
            return Response(
                {"error": "Invalid voting type"}, status=status.HTTP_400_BAD_REQUEST
            )
        return _execute_consensus(group_id, voting_type=voting_type, persist=False)


def _execute_consensus(group_id, voting_type, persist):
    try:
        topics, topic_names, user_ids, positions_data, expertise_data, labels_data = (
            get_user_data(group_id)
        )
    except ValueError as e:
        return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

    if voting_type == "non-positional-voting":
        sorted_rankings = VotingAlgorithms.schulze_voting_algorithm(
            positions_data, topic_names
        )
    else:
        sorted_rankings = VotingAlgorithms.calculate_positional_voting(
            topic_names, user_ids, positions_data, expertise_data
        )

    if persist:
        ConsensusResult.objects.filter(idGroup_identity_id=str(group_id)).delete()

    results = []
    for topic_name, final_value in sorted_rankings:
        topic = topics.get(topic_name=topic_name)
        if persist:
            ConsensusResult.objects.create(
                idGroup_identity_id=str(group_id),
                idGroup_snapshot={"id": str(group_id)},
                idTopic=topic,
                final_value=final_value,
            )
        labels = (
            labels_data[topic_name]
            if labels_data[topic_name]
            else ["There aren't labels"]
        )
        results.append(
            {
                "id_topic": topic.id,
                "topic_name": topic_name,
                "final_value": final_value,
                "labels": labels,
            }
        )

    if persist:
        channel_layer = get_channel_layer()
        async_to_sync(channel_layer.group_send)(
            f"phase3_group_{group_id}",
            {
                "type": "group_message",
                "message": {
                    "type": "consensus_calculation_completed",
                    "group_id": str(group_id),
                    "notification_message": "Consensus phase 3 calculations completed.",
                    "results": results,
                },
            },
        )

    return Response(
        {"message": "Consensus calculations completed.", "results": results},
        status=status.HTTP_200_OK,
    )
