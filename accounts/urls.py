from django.contrib.auth import views as auth_views
from django.urls import path

from .views import CustomLoginView, ForcePasswordChangeView, logout_view, staff_create, staff_list, staff_resend, signup, signup_done, signup_review, forgot_password, verify_reset_code, set_new_password

urlpatterns = [
    path("login/", CustomLoginView.as_view(), name="login"),
    path("logout/", logout_view, name="logout"),
    path("staff/", staff_list, name="staff_list"),
    path("staff/add/", staff_create, name="staff_create"),
    path("staff/<int:pk>/resend/", staff_resend, name="staff_resend"),
    path("password_change/", ForcePasswordChangeView.as_view(), name="password_change"),
    path("password_change/done/", auth_views.PasswordChangeDoneView.as_view(template_name="auth/password_change_done.html"), name="password_change_done"),
    path("signup/", signup, name="signup"),
    path("signup/done/", signup_done, name="signup_done"),
    path("signup/review/<int:pk>/", signup_review, name="signup_review"),
    path("password_reset/", forgot_password, name="password_reset"),
    path("password_reset/verify/", verify_reset_code, name="password_reset_verify"),
    path("password_reset/new/", set_new_password, name="password_reset_new"),
    path("password_reset/done/", auth_views.PasswordResetDoneView.as_view(template_name="auth/password_reset_done.html"), name="password_reset_done"),
    path("reset/<uidb64>/<token>/", auth_views.PasswordResetConfirmView.as_view(template_name="auth/password_reset_confirm.html"), name="password_reset_confirm"),
    path("reset/done/", auth_views.PasswordResetCompleteView.as_view(template_name="auth/password_reset_complete.html"), name="password_reset_complete"),
]
