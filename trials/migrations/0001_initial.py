import django.db.models.deletion
import django.utils.timezone
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        ("academics", "0003_program_batch_fields_and_seed"),
        ("students", "0007_father_name_optional_email"),
    ]

    operations = [
        migrations.CreateModel(
            name="TrialVisitor",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=150)),
                ("phone", models.CharField(max_length=20)),
                ("trial_date", models.DateField(default=django.utils.timezone.localdate)),
                ("notes", models.CharField(blank=True, max_length=255)),
                ("status", models.CharField(
                    choices=[("visited", "Visited"), ("joined", "Joined"), ("not_joining", "Not joining")],
                    db_index=True, default="visited", max_length=20,
                )),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("program", models.ForeignKey(
                    blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="+",
                    to="academics.program", verbose_name="Preferred batch",
                )),
                ("student", models.ForeignKey(
                    blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="+",
                    to="students.student",
                )),
            ],
            options={"ordering": ["-trial_date", "-id"]},
        ),
    ]
