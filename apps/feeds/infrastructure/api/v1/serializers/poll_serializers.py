from rest_framework import serializers

from apps.feeds.domain.entities.poll import Poll, PollOption, PollVote


class PollOptionSerializer(serializers.ModelSerializer):
    """Serializer para opciones de encuesta"""

    user_voted = serializers.SerializerMethodField()

    class Meta:
        model = PollOption
        fields = ["id", "text", "votes_count", "order", "user_voted"]
        read_only_fields = ["id", "votes_count", "user_voted"]

    def get_user_voted(self, obj):
        """Verifica si el usuario actual votó por esta opción"""
        request = self.context.get("request")
        if not request or not request.user.is_authenticated:
            return False

        return PollVote.objects.filter(
            user_identity_id=str(request.user.id), option=obj
        ).exists()


class PollSerializer(serializers.ModelSerializer):
    """Serializer para encuestas"""

    options = PollOptionSerializer(many=True, read_only=True)
    total_votes = serializers.ReadOnlyField()
    user_voted = serializers.SerializerMethodField()
    user_votes = serializers.SerializerMethodField()

    class Meta:
        model = Poll
        fields = [
            "id",
            "question",
            "is_multiple_choice",
            "is_anonymous",
            "allows_other",
            "expires_at",
            "is_active",
            "options",
            "total_votes",
            "user_voted",
            "user_votes",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "total_votes",
            "user_voted",
            "user_votes",
            "created_at",
            "updated_at",
        ]

    def get_user_voted(self, obj):
        """Verifica si el usuario actual ha votado en esta encuesta"""
        request = self.context.get("request")
        if not request or not request.user.is_authenticated:
            return False

        return PollVote.objects.filter(
            user_identity_id=str(request.user.id), poll=obj
        ).exists()

    def get_user_votes(self, obj):
        """Retorna las opciones que el usuario actual ha votado"""
        request = self.context.get("request")
        if not request or not request.user.is_authenticated:
            return []

        votes = PollVote.objects.filter(
            user_identity_id=str(request.user.id), poll=obj
        ).values_list("option_id", flat=True)

        return list(votes)


class PollCreateSerializer(serializers.ModelSerializer):
    """Serializer para crear encuestas"""

    options = serializers.ListField(
        child=serializers.CharField(max_length=200),
        min_length=2,
        max_length=10,
        write_only=True,
    )

    class Meta:
        model = Poll
        fields = [
            "question",
            "is_multiple_choice",
            "is_anonymous",
            "allows_other",
            "expires_at",
            "options",
        ]

    def validate_question(self, value):
        """Valida la pregunta de la encuesta"""
        if not value or len(value.strip()) == 0:
            raise serializers.ValidationError("La pregunta no puede estar vacía")
        if len(value) > 500:
            raise serializers.ValidationError(
                "La pregunta no puede exceder 500 caracteres"
            )
        return value.strip()

    def validate_options(self, value):
        """Valida las opciones de la encuesta"""
        if len(value) < 2:
            raise serializers.ValidationError("Debe haber al menos 2 opciones")
        if len(value) > 10:
            raise serializers.ValidationError("No puede haber más de 10 opciones")

        # Filtrar opciones vacías y duplicadas
        cleaned_options = []
        seen = set()

        for option in value:
            option_clean = option.strip()
            if option_clean and option_clean.lower() not in seen:
                cleaned_options.append(option_clean)
                seen.add(option_clean.lower())

        if len(cleaned_options) < 2:
            raise serializers.ValidationError("Debe haber al menos 2 opciones válidas")

        return cleaned_options

    def create(self, validated_data):
        """Crea la encuesta con sus opciones"""
        options_data = validated_data.pop("options")
        poll = Poll.objects.create(**validated_data)

        # Crear opciones
        for index, option_text in enumerate(options_data):
            PollOption.objects.create(poll=poll, text=option_text, order=index)

        return poll


class PollVoteSerializer(serializers.ModelSerializer):
    """Serializer para votos en encuestas"""

    class Meta:
        model = PollVote
        fields = ["id", "option", "created_at"]
        read_only_fields = ["id", "created_at"]

    def validate_option(self, value):
        """Valida que la opción pertenezca a una encuesta activa"""
        if not value.poll.is_active:
            raise serializers.ValidationError("Esta encuesta no está activa")

        if value.poll.is_expired:
            raise serializers.ValidationError("Esta encuesta ha expirado")

        return value

    def validate(self, attrs):
        """Validaciones adicionales"""
        user = self.context["request"].user
        option = attrs["option"]
        poll = option.poll

        # Verificar si ya votó (para encuestas de opción única)
        if not poll.is_multiple_choice:
            existing_vote = PollVote.objects.filter(
                user_identity_id=str(user.id), poll=poll
            ).exists()

            if existing_vote:
                raise serializers.ValidationError("Ya has votado en esta encuesta")
        else:
            # Para multiple choice, verificar que no vote la misma opción dos veces
            existing_vote = PollVote.objects.filter(
                user_identity_id=str(user.id), option=option
            ).exists()

            if existing_vote:
                raise serializers.ValidationError("Ya has votado por esta opción")

        return attrs

    def create(self, validated_data):
        """Crea el voto"""
        request_user = self.context["request"].user
        validated_data["user_identity_id"] = str(request_user.id)
        from apps.custom_auth.identity_principal import snapshot_from_principal

        validated_data["user_snapshot"] = snapshot_from_principal(request_user)
        validated_data["poll"] = validated_data["option"].poll
        return super().create(validated_data)
