from django.db import migrations

LINKED = [
    ("fees", "Payment"),
    ("registration", "CourseRegistration"),
    ("notifications_center", "Notification"),
    ("helpdesk", "Ticket"),
]


def pad_ids(apps, schema_editor):
    """Old short numbers such as "1" become "0001" (students and the copies of the ID kept on other records)."""
    Student = apps.get_model("students", "Student")
    taken_ids = set(Student.objects.values_list("student_id", flat=True))
    taken_regs = set(Student.objects.values_list("registration_number", flat=True))
    for s in Student.objects.order_by("pk"):
        old_id, old_reg = s.student_id, s.registration_number
        new_id = old_id.zfill(4) if old_id.isdigit() and len(old_id) < 4 else old_id
        new_reg = old_reg.zfill(4) if old_reg.isdigit() and len(old_reg) < 4 else old_reg
        if new_id != old_id and new_id not in taken_ids:
            taken_ids.discard(old_id)
            taken_ids.add(new_id)
            s.student_id = new_id
            for app, model in LINKED:
                apps.get_model(app, model).objects.filter(student_id_text=old_id).update(student_id_text=new_id)
        if new_reg != old_reg and new_reg not in taken_regs:
            taken_regs.discard(old_reg)
            taken_regs.add(new_reg)
            s.registration_number = new_reg
        s.save(update_fields=["student_id", "registration_number"])


class Migration(migrations.Migration):
    dependencies = [
        ("students", "0005_library_fields"),
        ("fees", "0003_payment_modes_receipts"),
        ("registration", "0001_initial"),
        ("notifications_center", "0001_initial"),
        ("helpdesk", "0001_initial"),
    ]

    operations = [migrations.RunPython(pad_ids, migrations.RunPython.noop)]
