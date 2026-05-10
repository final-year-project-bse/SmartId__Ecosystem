"""
Seed script — run with: python manage.py shell < seed_data.py
Populates all models with realistic dummy data.
"""
import os, django, random
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'smartid.settings')
django.setup()

from django.utils import timezone
from datetime import timedelta, time, datetime

from attendance.models import (
    Department, Location, Course, CourseEnrollment,
    TimetableSlot, AttendanceSession, AttendanceRecord, LeaveRequest, AccessLog,
)
from users.models import (
    User, ConsentRecord, UserAuthMethod, AuthMethod,
    RFIDCredential, ParentStudentLink, UniversityRecord,
)
from notifications.models import Notification

try:
    from dashboard.models import AlertRule, SystemDevice, FingerprintSensorSlot
    HAS_DASHBOARD_MODELS = True
except Exception:
    HAS_DASHBOARD_MODELS = False

print("🌱  Starting seed...")

# ─────────────────────────────────────────────
# 1. Departments
# ─────────────────────────────────────────────
dept_data = [
    ("Computer Science",      "CS"),
    ("Software Engineering",  "SE"),
    ("Electrical Engineering","EE"),
    ("Mathematics",           "MATH"),
    ("Business Administration","BBA"),
    ("Mechanical Engineering","ME"),
]
depts = {}
for name, code in dept_data:
    d, _ = Department.objects.get_or_create(code=code, defaults={"name": name})
    depts[code] = d
print(f"  Departments: {Department.objects.count()}")

# ─────────────────────────────────────────────
# 2. Locations
# ─────────────────────────────────────────────
loc_data = [
    ("Room 101",       "R101",  "classroom"),
    ("Room 102",       "R102",  "classroom"),
    ("Room 201",       "R201",  "classroom"),
    ("Room 202",       "R202",  "classroom"),
    ("CS Lab A",       "CLA",   "lab"),
    ("CS Lab B",       "CLB",   "lab"),
    ("Electronics Lab","ELB",   "lab"),
    ("Seminar Hall",   "SH1",   "hall"),
    ("Library",        "LIB",   "other"),
]
locs = {}
for name, code, ltype in loc_data:
    l, _ = Location.objects.get_or_create(code=code, defaults={"name": name, "location_type": ltype})
    locs[code] = l
print(f"  Locations: {Location.objects.count()}")

# ─────────────────────────────────────────────
# 3. University Records (pre-enrolled)
# ─────────────────────────────────────────────
uni_records = [
    ("CS-2021-003", "Hamza Malik",        "hamza.malik@uni.edu",     depts["CS"],   21, "03001111111"),
    ("CS-2021-004", "Zara Aslam",         "zara.aslam@uni.edu",      depts["CS"],   20, "03002222222"),
    ("CS-2021-005", "Usman Tariq",        "usman.tariq@uni.edu",     depts["CS"],   22, "03003333333"),
    ("SE-2022-001", "Sana Riaz",          "sana.riaz@uni.edu",       depts["SE"],   20, "03004444444"),
    ("SE-2022-002", "Bilal Ahmed",        "bilal.ahmed@uni.edu",     depts["SE"],   21, "03005555555"),
    ("EE-2021-001", "Nadia Khan",         "nadia.khan@uni.edu",      depts["EE"],   22, "03006666666"),
    ("EE-2021-002", "Omar Farooq",        "omar.farooq@uni.edu",     depts["EE"],   21, "03007777777"),
    ("MATH-2022-001","Ayesha Siddiqui",   "ayesha.s@uni.edu",        depts["MATH"], 20, "03008888888"),
    ("BBA-2022-001", "Kamran Iqbal",      "kamran.iqbal@uni.edu",    depts["BBA"],  21, "03009999999"),
    ("SE-2021-003",  "Maham Zafar",       "maham.zafar@uni.edu",     depts["SE"],   20, "03010101010"),
]
for reg, name, email, dept, age, phone in uni_records:
    UniversityRecord.objects.get_or_create(
        registration_number=reg,
        defaults={"full_name": name, "email": email, "department": dept, "age": age, "phone": phone},
    )
print(f"  UniversityRecords: {UniversityRecord.objects.count()}")

# ─────────────────────────────────────────────
# 4. Helper: create user + consent + auth method
# ─────────────────────────────────────────────
def make_user(email, first, last, role, gender, inst_id, dept=None, age=None, phone="", parent_contact="", password="Test@1234"):
    if User.objects.filter(email=email).exists():
        return User.objects.get(email=email)
    u = User.objects.create_user(
        email=email, password=password,
        first_name=first, last_name=last,
        institutional_id=inst_id, role=role,
        gender=gender, age=age, phone=phone,
        parent_contact=parent_contact,
        department=dept, is_active=True,
    )
    # Consent
    biometric = role != User.Role.PARENT
    ConsentRecord.objects.create(
        user=u,
        biometric_consent=biometric,
        rfid_consent=(role != User.Role.PARENT),
        data_retention_ack=True,
    )
    # Auth method
    if role == User.Role.STUDENT:
        primary = AuthMethod.RFID
        secondary = AuthMethod.FACE if gender == User.Gender.MALE else AuthMethod.FINGERPRINT
    elif role == User.Role.PROFESSOR:
        primary = AuthMethod.FACE if gender == User.Gender.MALE else AuthMethod.RFID
        secondary = ""
    elif role == User.Role.ADMIN:
        primary = AuthMethod.FINGERPRINT
        secondary = ""
    else:
        primary = ""; secondary = ""
    if primary:
        UserAuthMethod.objects.create(user=u, method=primary, secondary_method=secondary)
    return u

# ─────────────────────────────────────────────
# 5. Students
# ─────────────────────────────────────────────
students_data = [
    ("hamza.malik@student.smartid.com",   "Hamza",   "Malik",      "male",   "CS-2021-003", depts["CS"],   21, "03001111111", "03001111100"),
    ("zara.aslam@student.smartid.com",    "Zara",    "Aslam",      "female", "CS-2021-004", depts["CS"],   20, "03002222222", "03002222200"),
    ("usman.tariq@student.smartid.com",   "Usman",   "Tariq",      "male",   "CS-2021-005", depts["CS"],   22, "03003333333", "03003333300"),
    ("sana.riaz@student.smartid.com",     "Sana",    "Riaz",       "female", "SE-2022-001", depts["SE"],   20, "03004444444", "03004444400"),
    ("bilal.ahmed@student.smartid.com",   "Bilal",   "Ahmed",      "male",   "SE-2022-002", depts["SE"],   21, "03005555555", "03005555500"),
    ("nadia.khan@student.smartid.com",    "Nadia",   "Khan",       "female", "EE-2021-001", depts["EE"],   22, "03006666666", "03006666600"),
    ("omar.farooq@student.smartid.com",   "Omar",    "Farooq",     "male",   "EE-2021-002", depts["EE"],   21, "03007777777", "03007777700"),
    ("ayesha.s@student.smartid.com",      "Ayesha",  "Siddiqui",   "female", "MATH-2022-001",depts["MATH"],20, "03008888888", "03008888800"),
    ("kamran.iqbal@student.smartid.com",  "Kamran",  "Iqbal",      "male",   "BBA-2022-001",depts["BBA"],  21, "03009999999", "03009999900"),
    ("maham.zafar@student.smartid.com",   "Maham",   "Zafar",      "female", "SE-2021-003", depts["SE"],   20, "03010101010", "03010101000"),
]
students = []
for email, fn, ln, gender, inst_id, dept, age, phone, pcontact in students_data:
    u = make_user(email, fn, ln, User.Role.STUDENT, gender, inst_id, dept, age, phone, pcontact)
    students.append(u)
print(f"  Students: {len(students)}")

# ─────────────────────────────────────────────
# 6. Professors
# ─────────────────────────────────────────────
profs_data = [
    ("dr.ali.raza@staff.smartid.com",     "Ali",     "Raza",      "male",   "TCH-ali.raza",    depts["CS"]),
    ("dr.sara.noon@staff.smartid.com",    "Sara",    "Noon",      "female", "TCH-sara.noon",   depts["SE"]),
    ("dr.ahmed.baig@staff.smartid.com",   "Ahmed",   "Baig",      "male",   "TCH-ahmed.baig",  depts["EE"]),
    ("dr.hina.shah@staff.smartid.com",    "Hina",    "Shah",      "female", "TCH-hina.shah",   depts["MATH"]),
    ("dr.faisal.ali@staff.smartid.com",   "Faisal",  "Ali",       "male",   "TCH-faisal.ali",  depts["BBA"]),
]
profs = []
for email, fn, ln, gender, inst_id, dept in profs_data:
    u = make_user(email, fn, ln, User.Role.PROFESSOR, gender, inst_id, dept, age=40, phone="0300000000" )
    profs.append(u)
print(f"  Professors: {len(profs)}")

# ─────────────────────────────────────────────
# 7. Parents
# ─────────────────────────────────────────────
parents_data = [
    ("parent.malik@gmail.com",   "Tariq",   "Malik",   "male",   "PAR-parent.malik",   students[0]),   # Hamza's parent
    ("parent.aslam@gmail.com",   "Rashida", "Aslam",   "female", "PAR-parent.aslam",   students[1]),   # Zara's parent
    ("parent.tariq@gmail.com",   "Nasir",   "Tariq",   "male",   "PAR-parent.tariq",   students[2]),   # Usman's parent
    ("parent.riaz@gmail.com",    "Shahida", "Riaz",    "female", "PAR-parent.riaz",    students[3]),   # Sana's parent
    ("parent.ahmed@gmail.com",   "Khalid",  "Ahmed",   "male",   "PAR-parent.ahmed",   students[4]),   # Bilal's parent
]
for email, fn, ln, gender, inst_id, child in parents_data:
    p = make_user(email, fn, ln, User.Role.PARENT, gender, inst_id, phone="03000000001")
    ParentStudentLink.objects.get_or_create(parent=p, student=child)
print(f"  Parents created with links")

# ─────────────────────────────────────────────
# 8. Courses
# ─────────────────────────────────────────────
courses_data = [
    ("CS301", "Data Structures",         profs[0], locs["R101"], 3),
    ("CS401", "Operating Systems",       profs[0], locs["CLA"],  3),
    ("SE301", "Software Engineering",    profs[1], locs["R102"],  3),
    ("SE401", "Project Management",      profs[1], locs["SH1"],   2),
    ("EE301", "Digital Logic Design",    profs[2], locs["ELB"],   3),
    ("MATH301","Linear Algebra",         profs[3], locs["R201"],  3),
    ("BBA301", "Business Communication", profs[4], locs["R202"],  2),
]
courses = []
for code, name, prof, loc, credits in courses_data:
    c, _ = Course.objects.get_or_create(
        code=code,
        defaults={"name": name, "professor": prof, "location": loc, "is_active": True},
    )
    courses.append(c)
print(f"  Courses: {len(courses)}")

# ─────────────────────────────────────────────
# 9. Enroll students in courses
# ─────────────────────────────────────────────
enrollments = [
    # CS students → CS courses
    (students[0], courses[0]), (students[0], courses[1]),
    (students[1], courses[0]), (students[1], courses[1]),
    (students[2], courses[0]), (students[2], courses[1]),
    # SE students → SE courses
    (students[3], courses[2]), (students[3], courses[3]),
    (students[4], courses[2]), (students[4], courses[3]),
    (students[9], courses[2]), (students[9], courses[3]),
    # EE students → EE courses
    (students[5], courses[4]),
    (students[6], courses[4]),
    # MATH student
    (students[7], courses[5]),
    # BBA student
    (students[8], courses[6]),
    # Cross-enrollments
    (students[0], courses[5]), (students[2], courses[6]),
    (students[3], courses[5]), (students[4], courses[4]),
]
for stu, crs in enrollments:
    CourseEnrollment.objects.get_or_create(student=stu, course=crs)
print(f"  Enrollments: {CourseEnrollment.objects.count()}")

# ─────────────────────────────────────────────
# 10. Timetable Slots
# ─────────────────────────────────────────────
# day_of_week: 1=Mon, 2=Tue, 3=Wed, 4=Thu, 5=Fri
slots_data = [
    (courses[0], profs[0], locs["R101"],  1, time(8,0),  time(9,30)),
    (courses[0], profs[0], locs["R101"],  3, time(8,0),  time(9,30)),
    (courses[1], profs[0], locs["CLA"],   2, time(10,0), time(11,30)),
    (courses[1], profs[0], locs["CLA"],   4, time(10,0), time(11,30)),
    (courses[2], profs[1], locs["R102"],  1, time(11,0), time(12,30)),
    (courses[2], profs[1], locs["R102"],  3, time(11,0), time(12,30)),
    (courses[3], profs[1], locs["SH1"],   2, time(14,0), time(15,30)),
    (courses[4], profs[2], locs["ELB"],   1, time(9,0),  time(10,30)),
    (courses[4], profs[2], locs["ELB"],   4, time(9,0),  time(10,30)),
    (courses[5], profs[3], locs["R201"],  2, time(8,0),  time(9,30)),
    (courses[5], profs[3], locs["R201"],  4, time(8,0),  time(9,30)),
    (courses[6], profs[4], locs["R202"],  3, time(13,0), time(14,30)),
]
for crs, prof, loc, day, start, end in slots_data:
    TimetableSlot.objects.get_or_create(
        course=crs, professor=prof, location=loc, day_of_week=day,
        defaults={"start_time": start, "end_time": end},
    )
print(f"  TimetableSlots: {TimetableSlot.objects.count()}")

# ─────────────────────────────────────────────
# 11. Attendance Sessions + Records (last 14 days)
# ─────────────────────────────────────────────
today = timezone.now().date()
admin_user = User.objects.filter(role=User.Role.ADMIN).first()

session_count = 0
record_count = 0

for days_ago in range(1, 15):
    session_date = today - timedelta(days=days_ago)
    weekday = session_date.weekday() + 1  # 1=Mon..7=Sun
    if weekday > 5:
        continue  # skip weekends

    day_slots = TimetableSlot.objects.filter(day_of_week=weekday).select_related('course', 'location', 'professor')

    for slot in day_slots:
        start_dt = timezone.make_aware(datetime.combine(session_date, slot.start_time))
        end_dt   = timezone.make_aware(datetime.combine(session_date, slot.end_time))

        session, created = AttendanceSession.objects.get_or_create(
            course=slot.course,
            location=slot.location,
            started_at=start_dt,
            defaults={
                "ended_at": end_dt,
                "created_by": slot.professor,
            },
        )
        if not session.ended_at:
            session.ended_at = end_dt
            session.save(update_fields=["ended_at"])
        session_count += created

        # Enroll students who attend ~80% of the time
        enrolled = CourseEnrollment.objects.filter(course=slot.course).select_related("student")
        for enrollment in enrolled:
            if random.random() < 0.82:  # 82% attendance rate
                is_late = random.random() < 0.15
                marked_offset = timedelta(minutes=random.randint(2, 8) if not is_late else random.randint(10, 25))
                AttendanceRecord.objects.get_or_create(
                    user=enrollment.student,
                    session=session,
                    defaults={
                        "location": slot.location,
                        "marked_at": start_dt + marked_offset,
                        "status": AttendanceRecord.Status.LATE if is_late else AttendanceRecord.Status.ON_TIME,
                    },
                )
                record_count += 1

        # AccessLog for the session
        AccessLog.objects.create(
            user=slot.professor,
            location=slot.location,
            success=True,
            auth_method="face" if slot.professor.gender == "male" else "rfid",
            accessed_at=start_dt,
        )

print(f"  AttendanceSessions: {AttendanceSession.objects.count()}")
print(f"  AttendanceRecords:  {AttendanceRecord.objects.count()}")
print(f"  AccessLogs:         {AccessLog.objects.count()}")

# ─────────────────────────────────────────────
# 12. Leave Requests
# ─────────────────────────────────────────────
leave_data = [
    (students[0], courses[0], today - timedelta(days=3),  "Medical appointment",   "approved",  profs[0]),
    (students[1], courses[0], today - timedelta(days=5),  "Family emergency",      "approved",  profs[0]),
    (students[2], courses[1], today - timedelta(days=2),  "University sports event","pending",  None),
    (students[3], courses[2], today - timedelta(days=7),  "Sick leave",            "rejected",  profs[1]),
    (students[4], courses[2], today - timedelta(days=1),  "Personal reasons",      "pending",   None),
    (students[9], courses[3], today - timedelta(days=4),  "Exam in another subject","approved", profs[1]),
    (students[5], courses[4], today - timedelta(days=6),  "Lab equipment issue",   "pending",   None),
    (students[6], courses[4], today - timedelta(days=8),  "Transport strike",      "approved",  profs[2]),
]
for stu, crs, date, reason, status, reviewer in leave_data:
    lr, created = LeaveRequest.objects.get_or_create(
        student=stu, course=crs, date=date,
        defaults={
            "reason": reason,
            "status": status,
            "reviewed_by": reviewer,
            "reviewed_at": timezone.now() - timedelta(days=1) if reviewer else None,
        },
    )
print(f"  LeaveRequests: {LeaveRequest.objects.count()}")

# ─────────────────────────────────────────────
# 13. Notifications
# ─────────────────────────────────────────────
notif_data = [
    (students[0], "Missed Class",          "You were marked absent from CS301 on Monday.",               "missed_class"),
    (students[1], "Leave Request Approved","Your leave request for CS301 has been approved.",            "leave_request"),
    (students[2], "Missed Class",          "You were marked absent from CS401 on Wednesday.",            "missed_class"),
    (students[3], "Leave Request Rejected","Your leave request for SE301 has been rejected.",            "leave_request"),
    (students[4], "Missed Class",          "You were marked absent from SE301.",                         "missed_class"),
    (profs[0],    "Leave Request",         "Usman Tariq has submitted a leave request for CS401.",       "leave_request"),
    (profs[1],    "Leave Request",         "Sana Riaz has submitted a leave request for SE301.",         "leave_request"),
    (admin_user,  "System Alert",          "Attendance below threshold in CS301 for the past week.",     "system"),
]
for user, title, message, ntype in notif_data:
    if user:
        Notification.objects.get_or_create(
            user=user, title=title,
            defaults={"message": message, "notification_type": ntype, "read": False},
        )
print(f"  Notifications: {Notification.objects.count()}")

# ─────────────────────────────────────────────
# 14. Alert Rules
# ─────────────────────────────────────────────
if HAS_DASHBOARD_MODELS and admin_user:
    alert_rules_data = [
        ("CS301 Low Attendance",   courses[0], None,          75, "weekly"),
        ("SE301 Low Attendance",   courses[2], None,          70, "weekly"),
        ("Lab A Low Attendance",   None,       locs["CLA"],   60, "daily"),
        ("Overall Monthly Check",  None,       None,          65, "monthly"),
        ("EE Lab Attendance",      courses[4], None,          80, "weekly"),
    ]
    for name, course, location, threshold, window in alert_rules_data:
        if course or location:
            AlertRule.objects.get_or_create(
                name=name,
                defaults={
                    "course": course,
                    "location": location,
                    "threshold_pct": threshold,
                    "time_window": window,
                    "created_by": admin_user,
                    "is_active": True,
                },
            )
    print(f"  AlertRules: {AlertRule.objects.count()}")

# ─────────────────────────────────────────────
# 15. System Devices (Raspberry Pi)
# ─────────────────────────────────────────────
if HAS_DASHBOARD_MODELS and admin_user:
    import secrets
    devices_data = [
        ("Pi-Room101",  "raspberry_pi", locs["R101"]),
        ("Pi-Room102",  "raspberry_pi", locs["R102"]),
        ("Pi-LabA",     "raspberry_pi", locs["CLA"]),
        ("Pi-ELab",     "raspberry_pi", locs["ELB"]),
        ("Pi-SemHall",  "raspberry_pi", locs["SH1"]),
    ]
    devices = []
    for name, dtype, loc in devices_data:
        dev, created = SystemDevice.objects.get_or_create(
            name=name,
            defaults={
                "device_type": dtype,
                "location": loc,
                "api_key": secrets.token_hex(32),
                "is_active": True,
                "registered_by": admin_user,
            },
        )
        devices.append(dev)
    print(f"  SystemDevices: {SystemDevice.objects.count()}")

    # Fingerprint Slots
    if devices:
        slot_assignments = [
            (students[1], devices[0], 0),  # Zara → Pi-Room101, slot 0
            (students[3], devices[0], 1),  # Sana → Pi-Room101, slot 1
            (students[5], devices[3], 0),  # Nadia → Pi-ELab, slot 0
            (students[7], devices[1], 0),  # Ayesha → Pi-Room102, slot 0
            (students[9], devices[1], 1),  # Maham → Pi-Room102, slot 1
        ]
        for stu, dev, slot_num in slot_assignments:
            FingerprintSensorSlot.objects.get_or_create(
                device=dev, slot_number=slot_num,
                defaults={"user": stu},
            )
        print(f"  FingerprintSlots: {FingerprintSensorSlot.objects.count()}")

print("\n✅  Seed complete!")
print(f"     Users:      {User.objects.count()} total")
print(f"     Students:   {User.objects.filter(role='student').count()}")
print(f"     Professors: {User.objects.filter(role='professor').count()}")
print(f"     Parents:    {User.objects.filter(role='parent').count()}")
print(f"     Admins:     {User.objects.filter(role='admin').count()}")
print(f"     Sessions:   {AttendanceSession.objects.count()}")
print(f"     Records:    {AttendanceRecord.objects.count()}")
print(f"\n  All passwords: Test@1234")
