from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import (
    AIChatAPIView,
    AgentActionProposalViewSet,
    AgentPromptCurrentAPIView,
    KnowledgeChunkViewSet,
    KnowledgeDocumentViewSet,
    KnowledgeEntityViewSet,
    KnowledgeGraphViewSet,
    KnowledgeRelationViewSet,
    McpAdapterViewSet,
    ModelEndpointViewSet,
)

router = DefaultRouter()
router.register(r"knowledge_documents", KnowledgeDocumentViewSet)
router.register(r"knowledge_chunks", KnowledgeChunkViewSet)
router.register(r"knowledge_entities", KnowledgeEntityViewSet)
router.register(r"knowledge_relations", KnowledgeRelationViewSet)
router.register(r"model_endpoints", ModelEndpointViewSet)
router.register(r"mcp_adapters", McpAdapterViewSet)
router.register(r"knowledge_graph", KnowledgeGraphViewSet, basename="knowledge_graph")
router.register(r"agent_actions", AgentActionProposalViewSet, basename="agent_actions")

urlpatterns = [
    path("chat/", AIChatAPIView.as_view(), name="ai-chat"),
    path("agent_prompts/current/", AgentPromptCurrentAPIView.as_view(), name="agent-prompt-current"),
]
urlpatterns += router.urls
