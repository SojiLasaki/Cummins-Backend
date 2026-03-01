from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from apps.ai.models import AgentPromptConfig, KnowledgeChunk, KnowledgeDocument, McpAdapter


class AIApiTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.user = user_model.objects.create_user(
            username="ai_tester",
            email="ai_tester@example.com",
            password="test-pass-123",
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

    def test_agent_prompt_current_get_and_put(self):
        get_resp = self.client.get("/api/ai/agent_prompts/current/")
        self.assertEqual(get_resp.status_code, 200)
        self.assertIn("system_prompt", get_resp.data)
        self.assertIn("domain_guardrail_prompt", get_resp.data)

        put_resp = self.client.put(
            "/api/ai/agent_prompts/current/",
            {
                "system_prompt": "System prompt test",
                "domain_guardrail_prompt": "Guardrail prompt test",
            },
            format="json",
        )
        self.assertEqual(put_resp.status_code, 200)
        self.assertEqual(put_resp.data["system_prompt"], "System prompt test")

        saved = AgentPromptConfig.get_current()
        self.assertEqual(saved.domain_guardrail_prompt, "Guardrail prompt test")

    def test_knowledge_document_ingest_creates_chunks(self):
        resp = self.client.post(
            "/api/ai/knowledge_documents/ingest/",
            {
                "title": "Fuel Pump Notes",
                "content": "Cummins fuel pump inspection checklist relay pressure diagnostics.",
            },
            format="json",
        )
        self.assertEqual(resp.status_code, 201)
        doc_id = resp.data["id"]
        document = KnowledgeDocument.objects.get(id=doc_id)
        self.assertGreater(KnowledgeChunk.objects.filter(document=document).count(), 0)

    def test_knowledge_search_returns_results(self):
        ingest = self.client.post(
            "/api/ai/knowledge_documents/ingest/",
            {
                "title": "Injector Notes",
                "content": "Cummins injector diagnostics and service procedure for fuel rail pressure checks.",
            },
            format="json",
        )
        self.assertEqual(ingest.status_code, 201)

        search = self.client.get("/api/ai/knowledge_documents/search/", {"q": "injector diagnostics", "limit": 5})
        self.assertEqual(search.status_code, 200)
        self.assertIn("results", search.data)
        self.assertGreaterEqual(len(search.data["results"]), 1)

    def test_mcp_oauth_token_requires_oauth_auth_type(self):
        adapter = McpAdapter.objects.create(
            name="plain-mcp",
            base_url="http://localhost:8931/mcp",
            transport=McpAdapter.TRANSPORT_HTTP,
            auth_type=McpAdapter.AUTH_NONE,
            auth_config={},
        )

        resp = self.client.post(
            f"/api/ai/mcp_adapters/{adapter.id}/oauth_token/",
            {"access_token": "token-123"},
            format="json",
        )
        self.assertEqual(resp.status_code, 400)
        self.assertFalse(resp.data.get("ok", True))

    def test_mcp_oauth_token_saved(self):
        adapter = McpAdapter.objects.create(
            name="oauth-mcp",
            base_url="http://localhost:8931/mcp",
            transport=McpAdapter.TRANSPORT_HTTP,
            auth_type=McpAdapter.AUTH_OAUTH2,
            auth_config={},
        )

        resp = self.client.post(
            f"/api/ai/mcp_adapters/{adapter.id}/oauth_token/",
            {"access_token": "access-123", "refresh_token": "refresh-123"},
            format="json",
        )

        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.data.get("ok"))
        adapter.refresh_from_db()
        self.assertEqual(adapter.auth_config.get("access_token"), "access-123")
        self.assertEqual(adapter.auth_config.get("refresh_token"), "refresh-123")

    def test_mcp_start_oauth_requires_client_id(self):
        adapter = McpAdapter.objects.create(
            name="oauth-start-mcp",
            base_url="http://localhost:8931/mcp",
            transport=McpAdapter.TRANSPORT_HTTP,
            auth_type=McpAdapter.AUTH_OAUTH2,
            auth_config={},
        )

        resp = self.client.post(
            f"/api/ai/mcp_adapters/{adapter.id}/start_oauth/",
            {},
            format="json",
        )
        self.assertEqual(resp.status_code, 400)
        self.assertFalse(resp.data.get("ok", True))
        self.assertIn("client_id", str(resp.data.get("error") or ""))

    def test_mcp_oauth_status_requires_state(self):
        adapter = McpAdapter.objects.create(
            name="oauth-status-mcp",
            base_url="http://localhost:8931/mcp",
            transport=McpAdapter.TRANSPORT_HTTP,
            auth_type=McpAdapter.AUTH_OAUTH2,
            auth_config={"client_id": "abc123"},
        )

        resp = self.client.get(f"/api/ai/mcp_adapters/{adapter.id}/oauth_status/")
        self.assertEqual(resp.status_code, 400)
        self.assertFalse(resp.data.get("ok", True))

    def test_mcp_start_oauth_creates_pending_state(self):
        adapter = McpAdapter.objects.create(
            name="oauth-ready-mcp",
            base_url="https://example.com/mcp",
            transport=McpAdapter.TRANSPORT_HTTPS,
            auth_type=McpAdapter.AUTH_OAUTH2,
            auth_config={
                "client_id": "client-123",
                "authorize_url": "https://issuer.example.com/oauth/authorize",
                "token_url": "https://issuer.example.com/oauth/token",
                "scopes": "read write",
            },
        )

        start_resp = self.client.post(
            f"/api/ai/mcp_adapters/{adapter.id}/start_oauth/",
            {},
            format="json",
        )
        self.assertEqual(start_resp.status_code, 200)
        self.assertTrue(start_resp.data.get("ok"))
        state = start_resp.data.get("state")
        self.assertTrue(state)
        self.assertIn("authorization_url", start_resp.data)

        status_resp = self.client.get(
            f"/api/ai/mcp_adapters/{adapter.id}/oauth_status/",
            {"state": state},
        )
        self.assertEqual(status_resp.status_code, 200)
        self.assertEqual(status_resp.data.get("status"), "pending")
