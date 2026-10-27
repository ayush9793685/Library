from .models import AuditLog


def create_audit_log(*, user, action, object_modified="", old_value="", new_value="", ip_address=None, user_agent=""):
    AuditLog.objects.create(
        user=user if getattr(user, "is_authenticated", False) else None,
        action=action,
        object_modified=object_modified,
        old_value=old_value,
        new_value=new_value,
        ip_address=ip_address,
        user_agent=user_agent,
    )
