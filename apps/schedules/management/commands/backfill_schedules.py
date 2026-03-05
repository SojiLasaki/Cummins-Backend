"""
Create schedule rows for tickets that are already assigned but have no schedule.
Run once to fix "No schedules yet" for existing data:

    python manage.py backfill_schedules
"""
from django.core.management.base import BaseCommand

from apps.tickets.models import Ticket
from apps.schedules.models import Schedule
from apps.agents.assignment_agent import AssignmentAgent


class Command(BaseCommand):
    help = "Create schedules for assigned tickets that have none (backfill)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Only print what would be created, do not create.",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        agent = AssignmentAgent()

        # Tickets that have an assigned technician and customer
        tickets = Ticket.objects.filter(
            assigned_technician__isnull=False,
            customer__isnull=False,
        ).select_related("assigned_technician", "customer")

        created = 0
        skipped = 0
        for ticket in tickets:
            if Schedule.objects.filter(ticket=ticket).exists():
                skipped += 1
                continue
            if dry_run:
                self.stdout.write(
                    f"Would create schedule for ticket {ticket.ticket_id or ticket.id} "
                    f"(technician pk={ticket.assigned_technician_id})"
                )
                created += 1
                continue
            agent._ensure_schedule_for_assignment(ticket, ticket.assigned_technician)
            created += 1

        if dry_run:
            self.stdout.write(self.style.SUCCESS(f"Dry run: would create {created} schedule(s), skipped {skipped} (already have schedule)."))
        else:
            self.stdout.write(self.style.SUCCESS(f"Created {created} schedule(s). Skipped {skipped} ticket(s) that already had a schedule."))
