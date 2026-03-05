from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from apps.tickets.models import Ticket


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
