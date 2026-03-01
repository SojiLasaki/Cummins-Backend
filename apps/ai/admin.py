from django.contrib import admin

from .models import (
    AgentPromptConfig,
    KnowledgeChunk,
    KnowledgeDocument,
    KnowledgeEntity,
    KnowledgeRelation,
    McpAdapter,
    ModelEndpoint,
)


admin.site.register(KnowledgeDocument)
admin.site.register(KnowledgeChunk)
admin.site.register(KnowledgeEntity)
admin.site.register(KnowledgeRelation)
admin.site.register(ModelEndpoint)
admin.site.register(McpAdapter)
admin.site.register(AgentPromptConfig)
