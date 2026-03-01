from django.db import models


class KnowledgeDocument(models.Model):
    SOURCE_TEXT = "text"
    SOURCE_URL = "url"
    SOURCE_FILE = "file"
    SOURCE_MANUAL = "manual"
    SOURCE_OTHER = "other"

    SOURCE_TYPE_CHOICES = (
        (SOURCE_TEXT, "Text"),
        (SOURCE_URL, "URL"),
        (SOURCE_FILE, "File"),
        (SOURCE_MANUAL, "Manual"),
        (SOURCE_OTHER, "Other"),
    )

    source_type = models.CharField(max_length=32, choices=SOURCE_TYPE_CHOICES, default=SOURCE_TEXT)
    source_uri = models.CharField(max_length=1024, blank=True)
    title = models.CharField(max_length=255, blank=True)
    content = models.TextField(blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_by = models.ForeignKey(
        "users.User",
        on_delete=models.SET_NULL,
        related_name="knowledge_documents",
        null=True,
        blank=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["source_type"]),
            models.Index(fields=["title"]),
        ]

    def __str__(self):
        label = self.title or self.source_uri or f"doc-{self.pk}"
        return f"KnowledgeDocument<{label}>"


class KnowledgeChunk(models.Model):
    document = models.ForeignKey(KnowledgeDocument, on_delete=models.CASCADE, related_name="chunks")
    chunk_index = models.PositiveIntegerField()
    content = models.TextField()
    token_count = models.PositiveIntegerField(default=0)
    embedding = models.JSONField(default=list, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["document_id", "chunk_index"]
        constraints = [
            models.UniqueConstraint(fields=("document", "chunk_index"), name="unique_document_chunk_index"),
        ]

    def __str__(self):
        return f"KnowledgeChunk<doc={self.document_id}, idx={self.chunk_index}>"


class KnowledgeEntity(models.Model):
    name = models.CharField(max_length=255)
    entity_type = models.CharField(max_length=100, default="term")
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name", "entity_type"]
        constraints = [
            models.UniqueConstraint(fields=("name", "entity_type"), name="unique_entity_name_type"),
        ]

    def __str__(self):
        return f"{self.entity_type}:{self.name}"


class KnowledgeRelation(models.Model):
    source_entity = models.ForeignKey(
        KnowledgeEntity,
        on_delete=models.CASCADE,
        related_name="outgoing_relations",
    )
    target_entity = models.ForeignKey(
        KnowledgeEntity,
        on_delete=models.CASCADE,
        related_name="incoming_relations",
    )
    relation_type = models.CharField(max_length=100)
    weight = models.FloatField(default=1.0)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-weight", "-created_at"]
        indexes = [
            models.Index(fields=["relation_type"]),
        ]

    def __str__(self):
        return f"{self.source_entity_id} -[{self.relation_type}]-> {self.target_entity_id}"


class ModelEndpoint(models.Model):
    name = models.CharField(max_length=255, unique=True)
    provider = models.CharField(max_length=100)
    model_identifier = models.CharField(max_length=255)
    base_url = models.URLField(max_length=1024, blank=True)
    api_key_env = models.CharField(max_length=255, blank=True)
    is_default = models.BooleanField(default=False)
    is_enabled = models.BooleanField(default=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-is_default", "name"]
        indexes = [
            models.Index(fields=["is_enabled", "is_default"]),
        ]

    def __str__(self):
        return f"{self.provider}:{self.model_identifier}"


class McpAdapter(models.Model):
    TRANSPORT_HTTP = "http"
    TRANSPORT_HTTPS = "https"
    TRANSPORT_SSE = "sse"
    TRANSPORT_CHOICES = (
        (TRANSPORT_HTTP, "HTTP"),
        (TRANSPORT_HTTPS, "HTTPS"),
        (TRANSPORT_SSE, "SSE"),
    )

    AUTH_NONE = "none"
    AUTH_BEARER = "bearer"
    AUTH_API_KEY = "api_key"
    AUTH_OAUTH2 = "oauth2"
    AUTH_CUSTOM = "custom"
    AUTH_TYPE_CHOICES = (
        (AUTH_NONE, "None"),
        (AUTH_BEARER, "Bearer"),
        (AUTH_API_KEY, "API Key"),
        (AUTH_OAUTH2, "OAuth2 (FastMCP)"),
        (AUTH_CUSTOM, "Custom"),
    )

    name = models.CharField(max_length=255, unique=True)
    transport = models.CharField(max_length=32, choices=TRANSPORT_CHOICES, default=TRANSPORT_HTTP)
    base_url = models.URLField(max_length=1024)
    auth_type = models.CharField(max_length=32, choices=AUTH_TYPE_CHOICES, default=AUTH_NONE)
    auth_config = models.JSONField(default=dict, blank=True)
    is_enabled = models.BooleanField(default=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]
        indexes = [
            models.Index(fields=["is_enabled"]),
        ]

    def __str__(self):
        return self.name


class AgentPromptConfig(models.Model):
    slug = models.CharField(max_length=64, unique=True, default="current")
    system_prompt = models.TextField()
    domain_guardrail_prompt = models.TextField()
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at"]

    @classmethod
    def get_current(cls):
        defaults = {
            "system_prompt": (
                "You are Fix it Felix, an expert Cummins repair copilot. "
                "Prioritize fast ticket resolution, clear summaries, and actionable steps."
            ),
            "domain_guardrail_prompt": (
                "Only answer Cummins diagnostics, repair, maintenance, parts, and service workflow questions. "
                "Refuse non-domain topics with a brief redirect."
            ),
        }
        obj, _ = cls.objects.get_or_create(slug="current", defaults=defaults)
        return obj

    def __str__(self):
        return f"AgentPromptConfig<{self.slug}>"
