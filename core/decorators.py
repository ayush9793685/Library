from django.http import HttpResponseForbidden


def role_required(*allowed_roles):
    def decorator(view_func):
        def wrapper(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return HttpResponseForbidden("Authentication required")
            if request.user.is_staff:
                return view_func(request, *args, **kwargs)
            if getattr(request.user, "role", None) not in allowed_roles:
                return HttpResponseForbidden("Not allowed")
            return view_func(request, *args, **kwargs)

        return wrapper

    return decorator
