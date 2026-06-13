from flask import Flask, render_template, request, redirect, session
from datetime import datetime
import pymysql
import os
import urllib.parse
from dotenv import load_dotenv
from werkzeug.security import generate_password_hash, check_password_hash

# ================= INIT =================
app = Flask(__name__)
load_dotenv()

app.secret_key = os.getenv("SECRET_KEY", "dev_secret")

# ================= DB =================
def get_db():
    url = urllib.parse.urlparse(os.getenv("MYSQL_PUBLIC_URL"))

    return pymysql.connect(
        host=url.hostname,
        user=url.username,
        password=url.password,
        database=url.path.replace("/", ""),
        port=int(url.port),
        cursorclass=pymysql.cursors.DictCursor,
        autocommit=False
    )

# ================= HOME =================
@app.route("/")
def home():
    return render_template("home.html")

# ================= LOGIN PAGES =================
@app.route("/teacher-login")
def teacher_login():
    return render_template("teacher_login.html")

@app.route("/admin-login")
def admin_login():
    return render_template("admin_login.html")

# ================= REGISTER =================
@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        db = get_db()
        cursor = db.cursor()

        username = request.form["username"].strip().lower()
        password = generate_password_hash(request.form["password"])

        now = datetime.now().date()

        cursor.execute("""
            SELECT teacher_name, subject, checkin_time, status
            FROM attendance
            WHERE DATE(checkin_time)=CURDATE()
            ORDER BY checkin_time DESC
        """)

        db.commit()
        db.close()

        return redirect("/teacher-login")

    return render_template("register.html")
#==================== SAVE REGISTER =================   
@app.route("/save_register", methods=["POST"])
def save_register():
    db = get_db()
    cursor = db.cursor()

    fullname = request.form["fullname"]
    username = request.form["username"]
    password = generate_password_hash(request.form["password"])
    subject = request.form["subject"]
    email = request.form["email"]

    cursor.execute("""
        INSERT INTO teachers(full_name, username, password, subject, email)
        VALUES (%s,%s,%s,%s,%s)
    """, (fullname, username, password, subject, email))

    db.commit()
    db.close()

    return render_template("register.html", success="Account created successfully!")
# ================= LOGIN =================
@app.route("/login", methods=["POST"])
def login():
    db = get_db()
    cursor = db.cursor()

    username = request.form["username"].strip().lower()
    password = request.form["password"]

    cursor.execute("SELECT * FROM teachers WHERE username=%s", (username,))
    user = cursor.fetchone()

    db.close()

    if not user:
        return redirect("/teacher-login")

    if not check_password_hash(user["password"], password):
        return "Wrong password ❌"

    session["username"] = user["username"]
    session["role"] = user.get("role", "teacher")

    if session["role"] == "admin":
        return redirect("/admin")

    return redirect("/dashboard")

# ================= DASHBOARD =================
@app.route("/dashboard")
def dashboard():

    if "username" not in session:
        return redirect("/")

    db = get_db()
    cursor = db.cursor()

    username = session["username"]

    # Check kama teacher huyu amesha-check in leo
    cursor.execute("""
        SELECT id
        FROM attendance
        WHERE username=%s
        AND DATE(checkin_time)=CURDATE()
    """, (username,))

    already_checked = cursor.fetchone() is not None

    # Leta walimu wote walio-check in leo
    cursor.execute("""
        SELECT teacher_name,
               subject,
               TIME_FORMAT(checkin_time,'%H:%i') AS checkin_time,
               status
        FROM attendance
        WHERE DATE(checkin_time)=CURDATE()
        ORDER BY checkin_time ASC
    """)

    teachers = cursor.fetchall()

    db.close()

    return render_template(
        "dashboard.html",
        teachers=teachers,
        already_checked=already_checked
    )
    # ================= FORGOT PASSWORD =================
@app.route("/forgot_password")
def forgot_password():
    return render_template("forgot_password.html")

#==================== RESET PASSWORD =================

    email = request.form["email"]

    return f"Reset code sent to {email}"

#==================== SEND RESET CODE =================
@app.route("/send_reset_code", methods=["POST"])
def send_reset_code():
    email = request.form["email"]
    return f"Code sent to {email}"
    db = get_db()
    cursor = db.cursor()

    cursor.execute(
        "SELECT * FROM teachers WHERE email=%s",
        (email,)
    )

    teacher = cursor.fetchone()

    if not teacher:
        db.close()
        return "Email not found ❌"

    otp = str(random.randint(100000, 999999))

    otp_store[email] = otp

    msg = Message(
        "Password Reset Code",
        recipients=[email]
    )

    msg.body = f"""
Hello {teacher['full_name']},

Your password reset code is:

{otp}

Use this code to reset your password.
"""

    mail.send(msg)

    db.close()

    return render_template(
        "enter_code.html",
        email=email
    )
# ================= CHECKIN =================
@app.route("/checkin", methods=["POST"])
def checkin():
    if "username" not in session:
        return redirect("/teacher-login")

    username = session["username"]
    now = datetime.now()
    today = now.date()

    db = get_db()
    cursor = db.cursor()

    # CHECK IF ALREADY CHECKED IN
    cursor.execute("""
        SELECT id FROM attendance
        WHERE username=%s AND DATE(checkin_time)=CURDATE()
    """, (username,))

    if cursor.fetchone():
        db.close()
        session["msg"] = "Already checked in for today"
        return redirect("/dashboard")

    # GET TEACHER INFO
    cursor.execute("SELECT full_name, subject FROM teachers WHERE username=%s", (username,))
    teacher = cursor.fetchone()

    if not teacher:
        db.close()
        return "Teacher not found"

    # TIME CALC
    school_time = datetime.strptime("07:30:00", "%H:%M:%S").time()
    school_dt = datetime.combine(today, school_time)

    diff = int((now - school_dt).total_seconds() / 60)

    if diff <= 0:
        status = "On Time"
        late_text = f"Early by {abs(diff)//60}h {abs(diff)%60}m"
    else:
        status = "Late"
        late_text = f"Late by {diff//60}h {diff%60}m"

    final_status = f"{status} ({late_text})"

    # INSERT
    cursor.execute("""
        INSERT INTO attendance
        (username, teacher_name, subject, checkin_time, status)
        VALUES (%s,%s,%s,%s,%s)
    """, (
        username,
        teacher["full_name"],
        teacher["subject"],
        now,
        final_status
    ))

    db.commit()
    db.close()

    session["msg"] = "Check-in successful"
    return redirect("/dashboard")

# ================= ADMIN =================
@app.route("/admin")
def admin():
    if "username" not in session or session.get("role") != "admin":
        return redirect("/teacher-login")

    db = get_db()
    cursor = db.cursor()

    cursor.execute("SELECT * FROM teachers")
    teachers = cursor.fetchall()

    cursor.execute("""
        SELECT * FROM attendance
        ORDER BY checkin_time DESC
    """)
    attendance = cursor.fetchall()

    db.close()

    return render_template("admin.html", teachers=teachers, attendance=attendance)

# ================= LOGOUT =================
@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")

# ================= RUN =================
if __name__ == "__main__":
    app.run()