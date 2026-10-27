from django import forms
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from django.contrib.auth.password_validation import validate_password

from .models import SignupRequest, User


class UserCreateForm(UserCreationForm):
    class Meta:
        model = User
        fields = ("username", "email", "role", "is_active")


class StudentSelfUpdateForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ("email",)


class LoginForm(AuthenticationForm):
    remember_me = forms.BooleanField(
        required=False,
        initial=False,
        widget=forms.CheckboxInput(
            attrs={
                "class": "h-4 w-4 rounded border-slate-300 text-brand-700 focus:ring-brand-600",
            }
        ),
    )
    username = forms.CharField(
        widget=forms.TextInput(
            attrs={
                "class": "w-full rounded-xl border border-slate-300 bg-white px-4 py-3 text-[15px] text-slate-900 outline-none transition focus:border-blue-700 focus:ring-4 focus:ring-blue-100",
                "placeholder": "Enter username",
                "autocomplete": "username",
            }
        )
    )
    password = forms.CharField(
        widget=forms.PasswordInput(
            attrs={
                "class": "w-full rounded-xl border border-slate-300 bg-white px-4 py-3 text-[15px] text-slate-900 outline-none transition focus:border-blue-700 focus:ring-4 focus:ring-blue-100",
                "placeholder": "Enter password",
                "autocomplete": "current-password",
            }
        )
    )



class StaffCreateForm(forms.Form):
    first_name = forms.CharField(max_length=150)
    last_name = forms.CharField(max_length=150, required=False)
    username = forms.CharField(max_length=150)
    email = forms.EmailField()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs["class"] = "w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm outline-none focus:border-slate-600 focus:ring-2 focus:ring-slate-200"

    def clean_username(self):
        username = self.cleaned_data["username"].strip()
        if User.objects.filter(username__iexact=username).exists():
            raise forms.ValidationError("This username is already taken.")
        return username

    def clean_email(self):
        email = self.cleaned_data["email"].strip()
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("This email is already used by another account.")
        return email


_INPUT = "w-full rounded-xl border border-slate-300 bg-white px-4 py-3 text-[15px] text-slate-900 outline-none transition focus:border-blue-700 focus:ring-4 focus:ring-blue-100"


class SignupForm(forms.Form):
    username = forms.CharField(max_length=150)
    email = forms.EmailField()
    password = forms.CharField(widget=forms.PasswordInput)
    confirm_password = forms.CharField(widget=forms.PasswordInput)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs["class"] = _INPUT

    def clean_username(self):
        username = self.cleaned_data["username"].strip()
        if User.objects.filter(username__iexact=username).exists() or SignupRequest.objects.filter(
            username__iexact=username, status=SignupRequest.Status.PENDING
        ).exists():
            raise forms.ValidationError("This username is not available.")
        return username

    def clean_email(self):
        email = self.cleaned_data["email"].strip()
        if User.objects.filter(email__iexact=email).exists() or SignupRequest.objects.filter(
            email__iexact=email, status=SignupRequest.Status.PENDING
        ).exists():
            raise forms.ValidationError("This email already has an account or a pending request.")
        return email

    def clean(self):
        cleaned = super().clean()
        password = cleaned.get("password")
        if password and password != cleaned.get("confirm_password"):
            self.add_error("confirm_password", "Passwords do not match.")
        elif password:
            try:
                validate_password(password)
            except forms.ValidationError as exc:
                self.add_error("password", exc)
        return cleaned


class ForgotPasswordForm(forms.Form):
    email = forms.EmailField()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["email"].widget.attrs["class"] = _INPUT


class VerifyCodeForm(forms.Form):
    code = forms.CharField(max_length=6, min_length=6, label="6-digit code")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["code"].widget.attrs.update({"class": _INPUT, "inputmode": "numeric", "autocomplete": "one-time-code"})
