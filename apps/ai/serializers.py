from rest_framework import serializers

from .models import (
    AgentPromptConfig,
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
