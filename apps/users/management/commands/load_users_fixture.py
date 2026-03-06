"""
Load a user fixture after clearing any existing users that appear in the fixture.
Use when loaddata fails with UNIQUE constraint failed: users_profile.user_id
because those users/profiles already exist.

Disconnects User post_save signals during load so the fixture's Profile rows
are inserted without the signal creating duplicate profiles.
"""
import json
from django.db.models.signals import post_save
from django.core.management.base import BaseCommand, CommandError
from django.core.management import call_command
from django.contrib.auth import get_user_model


def _disconnect_user_signals():
    """Disconnect signals that create Profile/CustomerProfile on User save (so loaddata can insert them)."""
    User = get_user_model()
    from apps.users.signals import create_user_profiles
    post_save.disconnect(create_user_profiles, sender=User)
    try:
        from apps.customers.signals import create_customer_profile
        post_save.disconnect(create_customer_profile, sender=User)
    except ImportError:
        pass


def _reconnect_user_signals():
    """Reconnect after loaddata."""
    User = get_user_model()
    from apps.users import signals as user_signals
    post_save.connect(user_signals.create_user_profiles, sender=User)
    try:
        from apps.customers import signals as customer_signals
        post_save.connect(customer_signals.create_customer_profile, sender=User)
    except ImportError:
        pass


class Command(BaseCommand):
    help = (
        "Load a fixture that contains users.Profile / users.User. "
        "Deletes existing users whose pks appear in the fixture, disconnects "
        "User post_save signals, runs loaddata, then reconnects. "
        "Usage: python manage.py load_users_fixture users.json"
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "fixture_labels",
            nargs="+",
            type=str,
            help="Fixture file path(s), e.g. users.json",
        )

    def handle(self, *args, **options):
        User = get_user_model()
        fixture_labels = options["fixture_labels"]

        for label in fixture_labels:
            try:
                with open(label, "r", encoding="utf-8") as f:
                    data = json.load(f)
            except FileNotFoundError:
                raise CommandError(f"Fixture file not found: {label}")
            except json.JSONDecodeError as e:
                raise CommandError(f"Invalid JSON in {label}: {e}")

            if not isinstance(data, list):
                raise CommandError(f"Fixture {label} should be a JSON array of objects.")

            # Collect User pks from the fixture (app label "users", model "user")
            user_pks = set()
            for item in data:
                if not isinstance(item, dict):
                    continue
                model = item.get("model")
                if model and model.lower() == "users.user":
                    pk = item.get("pk")
                    if pk is not None:
                        user_pks.add(pk)

            if user_pks:
                deleted = User.objects.filter(pk__in=user_pks).delete()
                self.stdout.write(
                    self.style.WARNING(
                        f"Deleted {deleted[0]} existing user(s) (pk in {sorted(user_pks)}) before loading fixture."
                    )
                )
            else:
                self.stdout.write(
                    self.style.WARNING(f"No users.user entries found in {label}; loading anyway.")
                )

        _disconnect_user_signals()
        try:
            call_command("loaddata", *fixture_labels)
        finally:
            _reconnect_user_signals()
