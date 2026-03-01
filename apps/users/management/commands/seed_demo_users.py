from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Create or update local demo users with deterministic credentials."

    def handle(self, *args, **options):
        user_model = get_user_model()
        demo_users = [
            {"username": "admin", "email": "admin@example.com", "role": user_model.Roles.ADMIN},
            {"username": "office", "email": "office@example.com", "role": user_model.Roles.OFFICE},
            {"username": "engine", "email": "engine@example.com", "role": user_model.Roles.TECHNICIAN},
            {"username": "electrical", "email": "electrical@example.com", "role": user_model.Roles.TECHNICIAN},
            {"username": "customer", "email": "customer@example.com", "role": user_model.Roles.CUSTOMER},
            {"username": "login_probe", "email": "login_probe@example.com", "role": user_model.Roles.ADMIN},
        ]

        created = 0
        updated = 0

        for entry in demo_users:
            username = entry["username"]
            user, was_created = user_model.objects.get_or_create(
                username=username,
                defaults={
                    "email": entry["email"],
                    "role": entry["role"],
                    "is_active": True,
                },
            )

            changed = was_created
            if user.email != entry["email"]:
                user.email = entry["email"]
                changed = True
            if user.role != entry["role"]:
                user.role = entry["role"]
                changed = True
            if not user.is_active:
                user.is_active = True
                changed = True

            user.set_password(username)
            user.save()

            if was_created:
                created += 1
                self.stdout.write(self.style.SUCCESS(f"created {username}/{username}"))
            elif changed:
                updated += 1
                self.stdout.write(self.style.WARNING(f"updated {username}/{username}"))
            else:
                self.stdout.write(self.style.NOTICE(f"reset password {username}/{username}"))

        self.stdout.write(
            self.style.SUCCESS(f"seed complete: created={created}, updated={updated}, total={len(demo_users)}")
        )
