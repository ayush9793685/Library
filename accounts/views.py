import logging
import secrets
from datetime import timedelta

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.forms import SetPasswordForm
from django.contrib.auth.hashers import check_password, make_password
from django.utils import timezone
from django.contrib.auth import get_user_model, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.tokens import default_token_generator
from django.core.mail import get_connection, send_mail
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, render
from django.utils.crypto import get_random_string
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from django.contrib.auth.views import LoginView, PasswordChangeView
from django.shortcuts import redirect
from django.urls import reverse, reverse_lazy

from .forms import ForgotPasswordForm, LoginForm, SignupForm, StaffCreateForm, VerifyCodeForm
from .models import PasswordResetCode, SignupRequest


class CustomLoginView(LoginView):
    form_class = LoginForm
    template_name = "auth/login.html"

    def form_valid(self, form):
        remember_me = form.cleaned_data.get("remember_me")
        response = super().form_valid(form)
        if remember_me:
            self.request.session.set_expiry(1209600)  # 2 weeks
        else:
            self.request.session.set_expiry(0)  # expire on browser close
        return response


def logout_view(request):
    logout(request)
    return redirect("login")


class ForcePasswordChangeView(PasswordChangeView):
    template_name = "auth/password_change.html"
    success_url = reverse_lazy("password_change_done")

    def form_valid(self, form):
        response = super().form_valid(form)
        user = self.request.user
        if user.must_change_password:
            user.must_change_password = False
            user.save(update_fields=["must_change_password"])
        return response


def _email_config():
    """Reads sims/email_config.py directly so mail works whatever settings.py says."""
    try:
        from sims import email_config
        return (
            getattr(email_config, "EMAIL_HOST_USER", ""),
            getattr(email_config, "EMAIL_HOST_PASSWORD", ""),
            getattr(email_config, "OWNER_EMAIL", ""),
        )
    except ImportError:
        return "", "", ""


def _owner_email():
    return _email_config()[2] or getattr(settings, "OWNER_EMAIL", "")


def _safe_send(subject, message, from_email, recipient_list):
    """Send an email; if the mail server refuses, log it instead of crashing the page."""
    user, password, _ = _email_config()
    try:
        if user and password:
            connection = get_connection(
                backend="django.core.mail.backends.smtp.EmailBackend",
                host="smtp.gmail.com", port=587, username=user, password=password, use_tls=True,
            )
            return send_mail(subject, message, user, recipient_list, connection=connection)
        return send_mail(subject, message, from_email, recipient_list)
    except Exception:
        logging.getLogger(__name__).exception("EMAIL FAILED - could not send '%s' to %s", subject, recipient_list)
        return 0


def _send_setup_email(request, user):
    uid = urlsafe_base64_encode(force_bytes(user.pk))
    token = default_token_generator.make_token(user)
    link = request.build_absolute_uri(reverse("password_reset_confirm", kwargs={"uidb64": uid, "token": token}))
    _safe_send(
        "Set up your login",
        f"Hello {user.get_full_name() or user.username},\n\n"
        f"A management account has been created for you. Your username is: {user.username}\n\n"
        f"Open this link to choose your password:\n{link}\n\n"
        "If you forget your password later, use \"Forgot password?\" on the sign-in page "
        "and a reset link will be emailed to you.",
        None,
        [user.email],
    )


def _owner_only(request):
    return request.user.is_authenticated and request.user.is_superuser


@login_required
def staff_list(request):
    if not _owner_only(request):
        return HttpResponseForbidden("Only the owner can manage staff accounts.")
    User = get_user_model()
    staff = User.objects.filter(role=User.Role.ADMIN, is_superuser=False).order_by("username")
    pending = SignupRequest.objects.filter(status=SignupRequest.Status.PENDING).order_by("-created_at")
    return render(request, "auth/staff_list.html", {"staff": staff, "pending": pending})


@login_required
def staff_create(request):
    if not _owner_only(request):
        return HttpResponseForbidden("Only the owner can create staff accounts.")
    form = StaffCreateForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        User = get_user_model()
        user = User.objects.create_user(
            username=form.cleaned_data["username"],
            email=form.cleaned_data["email"],
            first_name=form.cleaned_data["first_name"],
            last_name=form.cleaned_data["last_name"],
            password=get_random_string(40),
            role=User.Role.ADMIN,
        )
        _send_setup_email(request, user)
        messages.success(request, f"Account created. A setup email was sent to {user.email}.")
        return redirect("staff_list")
    return render(request, "auth/staff_form.html", {"form": form})


@login_required
def staff_resend(request, pk):
    if not _owner_only(request):
        return HttpResponseForbidden("Only the owner can do this.")
    if request.method == "POST":
        user = get_object_or_404(get_user_model(), pk=pk, is_superuser=False)
        _send_setup_email(request, user)
        messages.success(request, f"Setup email sent again to {user.email}.")
    return redirect("staff_list")


# ---------- Sign up (needs the owner's approval) ----------

def signup(request):
    if request.user.is_authenticated:
        return redirect("dashboard:home")
    form = SignupForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        signup_request = SignupRequest.objects.create(
            username=form.cleaned_data["username"],
            email=form.cleaned_data["email"],
            password_hash=make_password(form.cleaned_data["password"]),
        )
        review_link = request.build_absolute_uri(reverse("signup_review", kwargs={"pk": signup_request.pk}))
        _safe_send(
            "New access request",
            f"Someone asked for access.\n\nUsername: {signup_request.username}\nEmail: {signup_request.email}\n\n"
            f"Review it here (sign in as the owner to approve or reject):\n{review_link}",
            None,
            [_owner_email()],
        )
        return redirect("signup_done")
    return render(request, "auth/signup.html", {"form": form})


def signup_done(request):
    return render(request, "auth/signup_done.html")


@login_required
def signup_review(request, pk):
    if not _owner_only(request):
        return HttpResponseForbidden("Only the owner can review access requests.")
    signup_request = get_object_or_404(SignupRequest, pk=pk)
    if request.method == "POST" and signup_request.status == SignupRequest.Status.PENDING:
        User = get_user_model()
        if request.POST.get("decision") == "approve":
            if User.objects.filter(username__iexact=signup_request.username).exists() or User.objects.filter(
                email__iexact=signup_request.email
            ).exists():
                messages.error(request, "A user with this username or email already exists.")
                return redirect("staff_list")
            user = User(username=signup_request.username, email=signup_request.email, role=User.Role.ADMIN)
            user.password = signup_request.password_hash
            user.save()
            signup_request.status = SignupRequest.Status.APPROVED
            signup_request.save(update_fields=["status"])
            _safe_send(
                "Your access was approved",
                f"Your access was approved. You can now sign in as {user.username}.",
                None,
                [user.email],
            )
            messages.success(request, f"Approved. {user.username} can sign in now.")
        else:
            signup_request.status = SignupRequest.Status.REJECTED
            signup_request.save(update_fields=["status"])
            messages.success(request, "Request rejected.")
        return redirect("staff_list")
    return render(request, "auth/signup_review.html", {"signup_request": signup_request})


# ---------- Forgot password with an emailed 6-digit code ----------

CODE_MINUTES = 10
MAX_CODE_ATTEMPTS = 5


def forgot_password(request):
    form = ForgotPasswordForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        email = form.cleaned_data["email"].strip()
        user = get_user_model().objects.filter(email__iexact=email, is_active=True).first()
        if user:
            code = f"{secrets.randbelow(1_000_000):06d}"
            PasswordResetCode.objects.filter(user=user, used=False).update(used=True)
            PasswordResetCode.objects.create(user=user, code_hash=make_password(code))
            _safe_send(
                "Your password reset code",
                f"Your code is {code}. It works for {CODE_MINUTES} minutes. If you did not ask for it, ignore this email.",
                None,
                [user.email],
            )
        # Same answer whether or not the email exists.
        request.session["reset_email"] = email
        return redirect("password_reset_verify")
    return render(request, "auth/forgot_password.html", {"form": form})


def verify_reset_code(request):
    email = request.session.get("reset_email")
    if not email:
        return redirect("password_reset")
    form = VerifyCodeForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = get_user_model().objects.filter(email__iexact=email, is_active=True).first()
        record = None
        if user:
            record = PasswordResetCode.objects.filter(user=user, used=False).order_by("-created_at").first()
        valid = False
        if record:
            expired = timezone.now() - record.created_at > timedelta(minutes=CODE_MINUTES)
            if expired or record.attempts >= MAX_CODE_ATTEMPTS:
                record.used = True
                record.save(update_fields=["used"])
            else:
                record.attempts += 1
                record.save(update_fields=["attempts"])
                valid = check_password(form.cleaned_data["code"], record.code_hash)
        if valid:
            record.used = True
            record.save(update_fields=["used"])
            request.session["reset_user_id"] = user.pk
            request.session["reset_verified_at"] = timezone.now().timestamp()
            return redirect("password_reset_new")
        form.add_error("code", "Wrong or expired code. Request a new one if needed.")
    return render(request, "auth/verify_code.html", {"form": form, "email": email})


def set_new_password(request):
    user_id = request.session.get("reset_user_id")
    verified_at = request.session.get("reset_verified_at", 0)
    if not user_id or timezone.now().timestamp() - verified_at > CODE_MINUTES * 60:
        return redirect("password_reset")
    user = get_object_or_404(get_user_model(), pk=user_id)
    form = SetPasswordForm(user, request.POST or None)
    if request.method == "POST" and form.is_valid():
        form.save()
        for key in ("reset_user_id", "reset_verified_at", "reset_email"):
            request.session.pop(key, None)
        messages.success(request, "Password changed. You can sign in now.")
        return redirect("login")
    return render(request, "auth/set_new_password.html", {"form": form})
