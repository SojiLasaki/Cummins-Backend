from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from apps.tickets.checklists import generate_ticket_checklist
from apps.tickets.models import Ticket, TicketResolutionPattern
from apps.tickets.patterns import upsert_pattern_from_completed_ticket


class TicketChecklistApiTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.user = user_model.objects.create_user(
            username="ticket_tester",
            email="ticket_tester@example.com",
            password="test-pass-123",
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

    def test_create_ticket_generates_checklist(self):
        resp = self.client.post(
            "/api/tickets/",
            {
                "title": "Engine overheating under load",
                "description": "Unit 4821 overheating and coolant loss after 20 minutes.",
                "specialization": "engine",
                "priority": 3,
                "severity": 3,
            },
            format="json",
        )
        self.assertEqual(resp.status_code, 201)
        self.assertIsInstance(resp.data.get("checklist_template"), list)
        self.assertGreater(len(resp.data.get("checklist_template")), 0)
        self.assertIsInstance(resp.data.get("checklist_progress"), list)
        self.assertTrue(str(resp.data.get("ticket_id") or "").strip())

    def test_update_checklist_progress_persists(self):
        ticket = Ticket.objects.create(
            ticket_id="TK-TEST-001",
            title="Coolant leak",
            description="Unit 5501 coolant leak near manifold",
            specialization="engine",
            created_by=self.user.username,
        )
        self.client.post(f"/api/tickets/{ticket.id}/regenerate_checklist/", {}, format="json")
        ticket.refresh_from_db()
        first_step = ticket.checklist_template[0]
        payload = [
            {
                "item_id": first_step["id"],
                "done": True,
                "note": "Completed and verified",
                "flagged": False,
                "time_minutes": 15,
                "photos": [],
            }
        ]
        resp = self.client.patch(
            f"/api/tickets/{ticket.id}/checklist_progress/",
            {"progress": payload},
            format="json",
        )
        self.assertEqual(resp.status_code, 200)
        progress = resp.data.get("checklist_progress") or []
        self.assertEqual(len(progress), 1)
        self.assertTrue(progress[0].get("done"))

    def test_update_checklist_progress_handles_invalid_minutes_gracefully(self):
        ticket = Ticket.objects.create(
            ticket_id="TK-TEST-004",
            title="Sensor issue",
            description="Invalid minute payload should not fail",
            specialization="electrical",
            created_by=self.user.username,
        )
        self.client.post(f"/api/tickets/{ticket.id}/regenerate_checklist/", {}, format="json")
        ticket.refresh_from_db()
        first_step = ticket.checklist_template[0]

        resp = self.client.patch(
            f"/api/tickets/{ticket.id}/checklist_progress/",
            {"progress": [{"item_id": first_step["id"], "done": True, "time_minutes": "abc"}]},
            format="json",
        )
        self.assertEqual(resp.status_code, 200)
        progress = resp.data.get("checklist_progress") or []
        self.assertEqual(progress[0].get("time_minutes"), 0)

    def test_update_checklist_progress_rejects_unknown_item(self):
        ticket = Ticket.objects.create(
            ticket_id="TK-TEST-002",
            title="Fuel pressure issue",
            description="Unit 7702 drops fuel pressure at idle",
            specialization="engine",
            created_by=self.user.username,
        )
        self.client.post(f"/api/tickets/{ticket.id}/regenerate_checklist/", {}, format="json")
        resp = self.client.patch(
            f"/api/tickets/{ticket.id}/checklist_progress/",
            {"progress": [{"item_id": "unknown-step", "done": True}]},
            format="json",
        )
        self.assertEqual(resp.status_code, 400)

    def test_regenerate_checklist_preserves_done_steps_with_same_ids(self):
        ticket = Ticket.objects.create(
            ticket_id="TK-TEST-003",
            title="Electrical warning",
            description="Truck 9021 alternator warning and voltage drop",
            specialization="electrical",
            created_by=self.user.username,
        )
        self.client.post(f"/api/tickets/{ticket.id}/regenerate_checklist/", {}, format="json")
        ticket.refresh_from_db()
        step_id = ticket.checklist_template[0]["id"]
        ticket.checklist_progress = [{"item_id": step_id, "done": True, "note": "done", "flagged": False, "time_minutes": 5, "photos": []}]
        ticket.save(update_fields=["checklist_progress"])

        resp = self.client.post(f"/api/tickets/{ticket.id}/regenerate_checklist/", {}, format="json")
        self.assertEqual(resp.status_code, 200)
        progress = resp.data.get("checklist_progress") or []
        matched = [item for item in progress if item.get("item_id") == step_id]
        self.assertTrue(matched)
        self.assertTrue(matched[0].get("done"))

    def test_completed_ticket_persists_resolution_pattern(self):
        ticket = Ticket.objects.create(
            ticket_id="TK-TEST-010",
            title="X15 fuel leak near pump",
            description="Leak observed around fuel pump hose clamp under load",
            issue_description="Fuel leak near pump hose clamp",
            specialization="engine",
            status="completed",
            created_by=self.user.username,
            checklist_template=[
                {"id": "s1", "category": "repair", "title": "Inspect fuel pump seals", "instructions": "Inspect seals", "required": True},
                {"id": "s2", "category": "repair", "title": "Replace damaged fuel hose", "instructions": "Replace hose", "required": True},
            ],
            checklist_progress=[
                {"item_id": "s1", "done": True},
                {"item_id": "s2", "done": True},
            ],
        )

        pattern = upsert_pattern_from_completed_ticket(ticket)
        self.assertIsNotNone(pattern)
        self.assertEqual(TicketResolutionPattern.objects.count(), 1)
        saved = TicketResolutionPattern.objects.first()
        self.assertEqual(saved.success_count, 1)
        self.assertGreaterEqual(len(saved.checklist_template), 2)

    def test_generate_checklist_uses_learned_pattern_for_similar_issue(self):
        learned = Ticket.objects.create(
            ticket_id="TK-TEST-011",
            title="X15 fuel leak near injector rail",
            description="Fuel leak around injector feed hose",
            issue_description="Fuel leak near injector rail",
            specialization="engine",
            status="completed",
            created_by=self.user.username,
            checklist_template=[
                {"id": "l1", "category": "repair", "title": "Inspect injector feed hose for cracks", "instructions": "Inspect hose", "required": True},
                {"id": "l2", "category": "repair", "title": "Replace injector hose clamp", "instructions": "Replace clamp", "required": True},
            ],
            checklist_progress=[
                {"item_id": "l1", "done": True},
                {"item_id": "l2", "done": True},
            ],
        )
        upsert_pattern_from_completed_ticket(learned)

        candidate = Ticket(
            ticket_id="TK-TEST-012",
            title="Injector fuel leak",
            description="Truck has fuel leak from injector hose connection",
            issue_description="Fuel leak from injector hose",
            specialization="engine",
            created_by=self.user.username,
        )

        generated = generate_ticket_checklist(
            candidate,
            diagnostic_payload={
                "specialization": "engine",
                "component_name": "X15 Engine",
                "issue": "Fuel leak at injector hose",
                "part_names": ["Fuel Injector", "Hose"],
            },
        )
        titles = [str(item.get("title") or "").lower() for item in generated.get("template", []) if isinstance(item, dict)]
        self.assertTrue(any("injector feed hose" in title for title in titles))
        provenance = generated.get("meta", {}).get("provenance", {})
        self.assertGreater(int(provenance.get("learned_steps") or 0), 0)

    def test_generate_checklist_does_not_use_unrelated_pattern(self):
        learned = Ticket.objects.create(
            ticket_id="TK-TEST-013",
            title="X15 fuel leak near injector rail",
            description="Fuel leak around injector feed hose",
            issue_description="Fuel leak near injector rail",
            specialization="engine",
            status="completed",
            created_by=self.user.username,
            checklist_template=[
                {"id": "u1", "category": "repair", "title": "Inspect injector feed hose for cracks", "instructions": "Inspect hose", "required": True},
            ],
            checklist_progress=[{"item_id": "u1", "done": True}],
        )
        upsert_pattern_from_completed_ticket(learned)

        unrelated = Ticket(
            ticket_id="TK-TEST-014",
            title="Battery charging fault",
            description="Alternator output drops intermittently",
            issue_description="Electrical charging issue",
            specialization="electrical",
            created_by=self.user.username,
        )
        generated = generate_ticket_checklist(
            unrelated,
            diagnostic_payload={
                "specialization": "electrical",
                "component_name": "Alternator",
                "issue": "Battery charging fault",
                "part_names": ["Alternator"],
            },
        )
        provenance = generated.get("meta", {}).get("provenance", {})
        self.assertEqual(int(provenance.get("learned_steps") or 0), 0)
