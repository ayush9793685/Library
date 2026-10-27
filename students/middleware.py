from django.utils import timezone

from .models import Student


class ExpireSubscriptionsMiddleware:
    """Deactivates students whose one-month subscription has ended.

    Runs at most once per calendar day per server process, on the first
    request of the day, so no scheduler is needed.
    """

    _last_run = None

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        today = timezone.localdate()
        # In test mode (a few seconds per subscription) check on every request.
        if Student._test_seconds() or ExpireSubscriptionsMiddleware._last_run != today:
            Student.expire_overdue()
            ExpireSubscriptionsMiddleware._last_run = today
        return self.get_response(request)
