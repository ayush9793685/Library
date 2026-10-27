from django.contrib.auth.signals import user_logged_in, user_logged_out
from django.dispatch import receiver

from .utils import create_audit_log


def _meta(request):
    ip = request.META.get("REMOTE_ADDR")
    ua = request.META.get("HTTP_USER_AGENT", "")
    return ip, ua


@receiver(user_logged_in)
def on_login(sender, request, user, **kwargs):
    ip, ua = _meta(request)
    create_audit_log(user=user, action="login", ip_address=ip, user_agent=ua)


@receiver(user_logged_out)
def on_logout(sender, request, user, **kwargs):
    ip, ua = _meta(request)
    create_audit_log(user=user, action="logout", ip_address=ip, user_agent=ua)
