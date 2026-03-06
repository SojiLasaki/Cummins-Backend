# Generated manually for predicted commute time and repair-time/cost system

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("tickets", "0004_ticket_checklists"),
    ]

    operations = [
        migrations.AddField(
            model_name="ticket",
            name="predicted_commute_time_minutes",
            field=models.IntegerField(
                blank=True,
                help_text="Predicted round-trip commute time in minutes (technician base to job site and back).",
                null=True,
            ),
        ),
    ]
