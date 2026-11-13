from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("students", "0006_four_digit_ids"),
    ]

    operations = [
        migrations.AddField(
            model_name="student",
            name="father_name",
            field=models.CharField(blank=True, max_length=150, verbose_name="Father's name"),
        ),
        migrations.AlterField(
            model_name="contactinformation",
            name="primary_email",
            field=models.EmailField(blank=True, max_length=254, null=True, unique=True),
        ),
    ]
