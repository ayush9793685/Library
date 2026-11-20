from django.db import migrations, models


class Migration(migrations.Migration):
    """Make the student's email optional in the database.

    0007 already declares this, but a database where 0007 was applied before that change
    (or only partly) still has primary_email NOT NULL, so registering without an email fails
    with "null value in column primary_email violates not-null constraint". Applying the same
    change again is harmless where the column is already nullable.
    """

    dependencies = [
        ("students", "0007_father_name_optional_email"),
    ]

    operations = [
        migrations.AlterField(
            model_name="contactinformation",
            name="primary_email",
            field=models.EmailField(blank=True, max_length=254, null=True, unique=True),
        ),
    ]
