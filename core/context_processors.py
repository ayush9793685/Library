def sidebar_menu(request):
    if not request.user.is_authenticated:
        return {"sidebar_links": []}

    admin_links = [
        ("Dashboard", "/dashboard/"),
        ("Students", "/students/"),
        ("Fees & Payments", "/fees/"),
        ("Announcements", "/notifications/"),
        ("Help Desk", "/helpdesk/"),
        ("Audit Logs", "/audits/"),
    ]

    student_links = [
        ("Dashboard", "/dashboard/"),
        ("My Profile", "/students/me/"),
        ("Academic Information", "/students/me/"),
        ("Fees & Payments", "/fees/"),
        ("Notifications", "/notifications/"),
        ("Activity History", "/audits/"),
        ("Help Desk", "/helpdesk/"),
        ("Security", "/accounts/password_change/"),
    ]

    is_admin = request.user.is_staff or getattr(request.user, "role", "") == "admin"
    if request.user.is_superuser:
        admin_links = admin_links + [("Staff Accounts", "/accounts/staff/")]
    return {"sidebar_links": admin_links if is_admin else student_links}