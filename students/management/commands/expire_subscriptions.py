from django.core.management.base import BaseCommand

from students.models import Student


class Command(BaseCommand):
    help = "Set students to Inactive when their subscription has expired."

    def handle(self, *args, **options):
        count = Student.expire_overdue()
        self.stdout.write(f"{count} student(s) set to Inactive.")
