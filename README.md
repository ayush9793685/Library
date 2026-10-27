# StudentHub — School Management System

A comprehensive, role-based **Student Information Management System** built with Django. Designed for schools and universities to manage students, academics, attendance, grades, fees, registrations, and administrative workflows — all from a single dashboard.

> **Project Status:** Active Development  
> **License:** MIT

![image_alt](https://github.com/tasmiul/student-management-system-django/blob/13e5a579cf99f40a742e89ca532477b7f2950012/Screenshots/HomePage.png)

---

## Table of Contents

- [Features](#features)
- [Screenshots](#screenshots)
- [Tech Stack](#tech-stack)
- [Project Structure](#project-structure)
- [Quick Start](#quick-start)
- [Default Credentials](#default-credentials)
- [Usage Guide](#usage-guide)
- [Deployment](#deployment)
- [Contributing](#contributing)
- [License](#license)

---

## Features

### 🔐 Authentication & Roles
- Custom `User` model with three roles: **Admin**, **Faculty**, **Student**
- Secure login with **Remember Me** (2-week session) or browser-close expiry
- Forced password change on first login
- Full password reset flow (email-based)

![image_alt](https://github.com/tasmiul/student-management-system-django/blob/1e58df8c10b64696867a849e82a6f4363f63afc4/Screenshots/login.png)

### 👥 Student Management
- Full **CRUD** for student profiles with auto-creation of login accounts
- Search by student ID, registration number, name, email, department, or program
- Filter by status (Active / Inactive / Graduated / Suspended), department, academic year
- Profile photo upload (JPG, JPEG, PNG, WebP)
- Role-based editing: students update limited fields; admins control everything
- Status toggle (suspend / activate) with audit trail

![image_alt](https://github.com/tasmiul/student-management-system-django/blob/354391429cc1bc739614666a174c2f81d4aa9977/Screenshots/student-list.png)

### 📚 Academics
- Manage **Departments**, **Programs**, **Courses**, and **Faculty**
- Department-program cascade validation
- Course-faculty assignment with instructor details
- Active/inactive status for all entities

![image_alt](https://github.com/tasmiul/student-management-system-django/blob/354391429cc1bc739614666a174c2f81d4aa9977/Screenshots/academics.png)

### 📋 Attendance Tracking
- Create attendance **sessions** by course, department, program, semester, and time slot
- Auto-enrollment of students matching session criteria
- Single-page **marking interface** with per-student status (Present / Absent / Late / Excused) and remarks
- Bulk **Mark All Present** shortcut
- Admin dashboard with low-attendance alerts (< 75%) and monthly trend chart
- Student view with per-course attendance percentage
- Export to **CSV**, **Excel**, and **PDF**

![image_alt](https://github.com/tasmiul/student-management-system-django/blob/354391429cc1bc739614666a174c2f81d4aa9977/Screenshots/attendance-mark.png)

### 📝 Gradebook & Results
- Create exams (Quiz, Assignment, Midterm, Final) linked to courses with **total marks**
- Per-student marks entry for enrolled students with automatic **letter grade** and **GPA** calculation
- Publish/unpublish results to control student visibility
- Student view with semester-wise GPA, cumulative CGPA, and full transcript
- Grading scale: 4.00 (A+ = 80%, A = 75%, … F < 40%)
- Export to **CSV**, **Excel**, and printable **Transcript PDF**

![image_alt](https://github.com/tasmiul/student-management-system-django/blob/354391429cc1bc739614666a174c2f81d4aa9977/Screenshots/grade-entry.png)
![image_alt](https://github.com/tasmiul/student-management-system-django/blob/354391429cc1bc739614666a174c2f81d4aa9977/Screenshots/student-results.png)

### 📦 Course Registration
- Define **registration windows** with start/end dates and active toggles
- Create **course offerings** linked to courses, semesters, and capacity limits
- Students browse available offerings and register with one click
- Admin approval workflow — approved registrations auto-create attendance enrollments
- Students can drop courses within active windows

![image_alt](https://github.com/tasmiul/student-management-system-django/blob/354391429cc1bc739614666a174c2f81d4aa9977/Screenshots/registration-admin.png)
![image_alt](https://github.com/tasmiul/student-management-system-django/blob/354391429cc1bc739614666a174c2f81d4aa9977/Screenshots/registration-student.png)

### 💰 Fees & Payments
- Define **fee structures** by fee type (Tuition, Registration, Lab, Library, Examination), academic year, and semester
- Record payments against fee structures per student
- **Per-student lookup**: select a student to view expected fees, payment history, and outstanding balance
- Student view: personal fee summary with total expected, paid, and due amount
- Aggregate collection total for administrators

![image_alt](https://github.com/tasmiul/student-management-system-django/blob/354391429cc1bc739614666a174c2f81d4aa9977/Screenshots/fees-admin.png)
![image_alt](https://github.com/tasmiul/student-management-system-django/blob/354391429cc1bc739614666a174c2f81d4aa9977/Screenshots/fees-student.png)

### 📄 Document Management
- Upload documents by category: Calendar, Enrollment Certificate, Transcript, Notice, Circular, ID Card
- Visibility control: public documents visible to all students; admin-only for internal use

### 🔔 Announcements & Notifications
- Create announcements with publish/expiry dates, optional department and semester targeting
- Students see only announcements relevant to their department and semester

### 🎫 Helpdesk / Support Tickets
- Students raise support tickets (Academic, Technical, Financial, General)
- Status workflow: Open → In Progress → Resolved → Closed
- Threaded replies with author tracking
- Admins see all tickets; students see only their own

![image_alt](https://github.com/tasmiul/student-management-system-django/blob/354391429cc1bc739614666a174c2f81d4aa9977/Screenshots/helpdesk.png)
![image_alt](https://github.com/tasmiul/student-management-system-django/blob/354391429cc1bc739614666a174c2f81d4aa9977/Screenshots/helpdesk-detail.png)

### 📊 Admin Dashboard
- Real-time stats: total/active/inactive/graduated/suspended students
- Bar charts for students by department and academic year
- Quick-action links to all modules
- Recent registrations and profile updates

![image_alt](https://github.com/tasmiul/student-management-system-django/blob/354391429cc1bc739614666a174c2f81d4aa9977/Screenshots/admin-dashboard.png)

### 👤 Student Dashboard
- Welcome message with profile completion percentage
- Profile summary (ID, registration number, department, program)
- Recent activity log

![image_alt](https://github.com/tasmiul/student-management-system-django/blob/354391429cc1bc739614666a174c2f81d4aa9977/Screenshots/student-dashboard.png)

### 📈 Audit Trail
- Automatic logging of login/logout events via signals
- Manual logging on all student CRUD and profile update operations
- Records user, action, object, old/new values, IP address, user agent, timestamp
- Dedicated audit log viewer for administrators

### 📉 Reports
- CSV export of student directory with all key fields

---

## Screenshots
[Screenshots](https://github.com/tasmiul/student-management-system-django/tree/354391429cc1bc739614666a174c2f81d4aa9977/Screenshots)

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| **Backend** | [Django 5.0+](https://www.djangoproject.com/) (Python) |
| **Database** | SQLite3 (development) — easily swappable to PostgreSQL / MySQL |
| **Frontend** | [Tailwind CSS](https://tailwindcss.com/) (CDN), [Alpine.js](https://alpinejs.dev/) (CDN), [Manrope](https://fonts.google.com/specimen/Manrope) (Google Fonts) |
| **Authentication** | Django Auth + Custom User Model with roles |
| **Session Management** | Django Sessions with configurable expiry |
| **File Storage** | Django FileSystem (local `media/` directory) |
| **Task Queue** | None (synchronous) — suitable for single-server deployment |
| **Web Server** | Gunicorn + Nginx (see `deploy/` for config) |
| **Charts** | CSS-based (no external charting library — easy to add Chart.js) |

---

## Project Structure

```
School Management System/
├── sims/                    # Django project settings and main URL router
├── accounts/                # Custom User model, authentication, login/logout
├── academics/               # Departments, Programs, Courses, Faculty
├── students/                # Student profiles, contact, addresses, emergency
├── attendance/              # Attendance sessions, records, enrollments, exports
├── gradebook/               # Exams, grade records, GPA/CGPA calculation
├── registration/            # Registration windows, course offerings, approvals
├── fees/                    # Fee structures, payments, per-student breakdown
├── documents/               # File uploads (calendars, transcripts, notices, etc.)
├── notifications_center/    # Announcements and notifications
├── helpdesk/                # Support tickets and threaded replies
├── audits/                  # Audit logging (signals + middleware + viewer)
├── dashboard/               # Admin and student role-based dashboards
├── reports/                 # CSV data exports
├── core/                    # Utility app (context processors, decorators)
├── templates/               # All project templates (Tailwind + Alpine.js)
├── static/                  # Static assets
├── media/                   # User-uploaded files (profile photos, documents)
├── deploy/                  # Deployment configs (Gunicorn, Nginx)
├── requirements.txt         # Python dependencies
└── manage.py                # Django management script
```

---

## Quick Start

### Prerequisites
- Python 3.10+
- pip

### Installation

```bash
# 1. Clone the repository
git clone https://github.com/tasmiul/student-management-system-django.git
cd school-management-system

# 2. Create and activate a virtual environment
python -m venv env
# Windows:
env\Scripts\activate
# macOS / Linux:
source env/bin/activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Run migrations
python manage.py migrate

# 5. Create a superuser (admin)
python manage.py createsuperuser

# 6. (Optional) Load demo data
python manage.py seed_demo

# 7. Start the development server
python manage.py runserver

# 8. Open in browser
#    http://127.0.0.1:8000/
```

---

## Default Credentials

> **⚠️ Change these immediately in production.**

After running `seed_demo`:

| Role | Username | Password |
|------|----------|----------|
| **Admin** | `admin` | `Admin@12345` |
| **Student** | `student1` | `Student@12345` |

The demo student account will be prompted to change password on first login.

---

## Usage Guide

### For Administrators
1. **Login** with admin credentials
2. **Dashboard** shows overall stats and quick links
3. **Students** → Add, edit, search, filter, and manage student records
4. **Academics** → Set up departments, programs, courses, and faculty
5. **Attendance** → Create sessions and mark attendance per course
6. **Gradebook** → Create exams, enter marks, publish results
7. **Registration** → Create registration windows and course offerings; approve student registrations
8. **Fees** → Define fee structures; record payments; view per-student breakdowns

### For Students
1. **Login** with student credentials
2. **Dashboard** shows your profile summary and recent activity
3. **My Profile** → View and edit personal information and upload photo
4. **Attendance** → View your attendance percentage per course
5. **Results** → View semester-wise GPA and CGPA; download transcript
6. **Registration** → Browse and register for available course offerings
7. **Fees** → View your fee summary and payment history
8. **Helpdesk** → Submit support tickets and track their status

---

## Deployment

Sample Gunicorn and Nginx configuration files are located in the `deploy/` directory:

- `deploy/gunicorn.service.example` — systemd service file
- `deploy/nginx.conf.example` — Nginx reverse proxy configuration

### Production Checklist
- [ ] Set `DEBUG=False` and configure `ALLOWED_HOSTS` in `sims/settings.py`
- [ ] Use a strong, unique `SECRET_KEY` (move to environment variable)
- [ ] Configure a production database (PostgreSQL or MySQL)
- [ ] Set up a proper email backend (SMTP) for password resets
- [ ] Serve static and media files via Nginx or a CDN
- [ ] Use HTTPS with a valid SSL certificate
- [ ] Change all default credentials

---

## License

This project is licensed under the **MIT License**. See the [LICENSE](LICENSE) file for details.

```
MIT License

Copyright (c) 2026 Tasmiul Alam Shopnil

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

---

## Acknowledgments

- Built with [Django](https://www.djangoproject.com/)
- UI styled with [Tailwind CSS](https://tailwindcss.com/)
- Interactive features powered by [Alpine.js](https://alpinejs.dev/)
- Font by [Manrope](https://fonts.google.com/specimen/Manrope) via Google Fonts
