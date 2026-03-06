from rest_framework import serializers

from .models import (
    AgentActionProposal,
    AgentExecutionTrace,
    AgentPromptConfig,
    FelixChatMessage,
    FelixChatThread,
    KnowledgeChunk,
    KnowledgeDocument,
    KnowledgeEntity,
    KnowledgeRelation,
    McpAdapter,
    ModelEndpoint,
)


class KnowledgeDocumentSerializer(serializers.ModelSerializer):
    class Meta:
        model = KnowledgeDocument
        fields = "__all__"
        read_only_fields = ("created_at", "updated_at")


class KnowledgeDocumentIngestSerializer(serializers.Serializer):
    title = serializers.CharField(max_length=255, required=False, allow_blank=True)
    content = serializers.CharField(required=False, allow_blank=True)
    url = serializers.URLField(required=False, allow_blank=True)
    metadata = serializers.JSONField(required=False)
    chunk_size = serializers.IntegerField(required=False, min_value=1, default=120)
    overlap = serializers.IntegerField(required=False, min_value=0, default=20)
    timeout_seconds = serializers.IntegerField(required=False, min_value=1, max_value=60, default=15)

    def validate(self, attrs):
        content = (attrs.get("content") or "").strip()
        url = (attrs.get("url") or "").strip()
        if not content and not url:
            raise serializers.ValidationError("Provide either 'content' or 'url'.")
        attrs["content"] = content
        attrs["url"] = url
        return attrs


class KnowledgeChunkSerializer(serializers.ModelSerializer):
    document_title = serializers.CharField(source="document.title", read_only=True)

    class Meta:
        model = KnowledgeChunk
        fields = "__all__"
        read_only_fields = ("created_at",)


class KnowledgeEntitySerializer(serializers.ModelSerializer):
    class Meta:
        model = KnowledgeEntity
        fields = "__all__"
        read_only_fields = ("created_at",)


class KnowledgeRelationSerializer(serializers.ModelSerializer):
    source_entity_name = serializers.CharField(source="source_entity.name", read_only=True)
    target_entity_name = serializers.CharField(source="target_entity.name", read_only=True)

    class Meta:
        model = KnowledgeRelation
        fields = "__all__"
        read_only_fields = ("created_at",)


class ModelEndpointSerializer(serializers.ModelSerializer):
    class Meta:
        model = ModelEndpoint
        fields = "__all__"
        read_only_fields = ("created_at", "updated_at")


class McpAdapterSerializer(serializers.ModelSerializer):
    class Meta:
        model = McpAdapter
        fields = "__all__"
        read_only_fields = ("created_at", "updated_at")


class AgentPromptConfigSerializer(serializers.ModelSerializer):
    class Meta:
        model = AgentPromptConfig
        fields = ("system_prompt", "domain_guardrail_prompt", "updated_at")
        read_only_fields = ("updated_at",)


class AgentExecutionTraceSerializer(serializers.ModelSerializer):
    adapter_name = serializers.CharField(source="adapter.name", read_only=True)

    class Meta:
        model = AgentExecutionTrace
        fields = "__all__"
        read_only_fields = ("created_at",)


class AgentActionProposalSerializer(serializers.ModelSerializer):
    created_by_username = serializers.CharField(source="created_by.username", read_only=True)
    approved_by_username = serializers.CharField(source="approved_by.username", read_only=True)
    traces = AgentExecutionTraceSerializer(many=True, read_only=True)

    class Meta:
        model = AgentActionProposal
        fields = "__all__"
        read_only_fields = (
            "result",
            "error",
            "created_at",
            "approved_at",
            "executed_at",
            "updated_at",
        )


class FelixChatMessageSerializer(serializers.ModelSerializer):
    class Meta:
        model = FelixChatMessage
        fields = ("id", "role", "content", "metadata", "created_at")
        read_only_fields = ("id", "created_at")


class FelixChatThreadSerializer(serializers.ModelSerializer):
    message_count = serializers.IntegerField(read_only=True)
    is_shared = serializers.SerializerMethodField()
    last_message_preview = serializers.SerializerMethodField()

    class Meta:
        model = FelixChatThread
        fields = (
            "id",
            "title",
            "message_count",
            "is_shared",
            "last_message_preview",
            "last_message_at",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "message_count", "is_shared", "last_message_preview", "last_message_at", "created_at", "updated_at")

    def get_is_shared(self, obj: FelixChatThread) -> bool:
        return bool(obj.shared_token)

    def get_last_message_preview(self, obj: FelixChatThread) -> str:
        message = obj.messages.order_by("-created_at").values_list("content", flat=True).first()
        if not message:
            return ""
        text = str(message).strip().replace("\n", " ")
        return text[:140]


class FelixChatThreadDetailSerializer(FelixChatThreadSerializer):
    messages = FelixChatMessageSerializer(many=True, read_only=True)

    class Meta(FelixChatThreadSerializer.Meta):
        fields = FelixChatThreadSerializer.Meta.fields + ("messages", "shared_at")
        read_only_fields = FelixChatThreadSerializer.Meta.read_only_fields + ("messages", "shared_at")
