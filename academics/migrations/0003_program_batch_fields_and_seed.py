import datetime
from decimal import Decimal

from django.db import migrations, models

BATCHES = [
    # name, code, fee, shift, start, end
    ("Pratibha", "PRATIBHA", Decimal("500"), "morning", datetime.time(7, 0), datetime.time(14, 0)),
    ("Pragati", "PRAGATI", Decimal("600"), "afternoon", datetime.time(14, 30), datetime.time(22, 0)),
    ("Sankalp", "SANKALP", Decimal("1000"), "full_day", datetime.time(7, 0), datetime.time(22, 0)),
]


def seed_batches(apps, schema_editor):
    Department = apps.get_model("academics", "Department")
    Program = apps.get_model("academics", "Program")
    department = Department.objects.filter(code="GEN").first()
    if department is None:
        name = "General"
        if Department.objects.filter(name=name).exists():
            name = "General (default)"
        department = Department.objects.create(name=name, code="GEN")
    for name, code, fee, shift, start, end in BATCHES:
        program = Program.objects.filter(name__iexact=name).first()
        if program is None:
            Program.objects.create(
                department=department, name=name, code=code, monthly_fee=fee,
                shift=shift, start_time=start, end_time=end, is_active=True,
            )
        else:
            # An existing program with this name is adopted as the batch.
            program.monthly_fee, program.shift = fee, shift
            program.start_time, program.end_time = start, end
            program.save()


class Migration(migrations.Migration):

    dependencies = [
        ("academics", "0002_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="program",
            name="monthly_fee",
            field=models.DecimalField(decimal_places=2, default=0, max_digits=10),
        ),
        migrations.AddField(
            model_name="program",
            name="shift",
            field=models.CharField(
                choices=[("morning", "Morning shift"), ("afternoon", "Afternoon shift"), ("full_day", "Full day")],
                default="full_day",
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name="program",
            name="start_time",
            field=models.TimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="program",
            name="end_time",
            field=models.TimeField(blank=True, null=True),
        ),
        migrations.RunPython(seed_batches, migrations.RunPython.noop),
    ]
