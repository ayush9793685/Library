from datetime import date

from django.core.management.base import BaseCommand
from django.utils import timezone

from attendance.services import mark_absentees


class Command(BaseCommand):
    help = "Mark active students with no scan/record as Absent for a day (default: today). Skips holidays."

    def add_arguments(self, parser):
        parser.add_argument("--date", help="YYYY-MM-DD (default today)")

    def handle(self, *args, **options):
        day = date.fromisoformat(options["date"]) if options.get("date") else timezone.localdate()
        count = mark_absentees(day)
        if count is None:
            self.stdout.write(f"{day} is a holiday: nobody marked Absent.")
        else:
            self.stdout.write(f"{count} student(s) marked Absent for {day}.")
