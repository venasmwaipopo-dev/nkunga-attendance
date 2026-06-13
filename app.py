from flask import Flask, render_template, request, redirect, session
from datetime import datetime, timedelta
import pymysql
from flask_mail import Mail, Message
import random
import os
import urllib.parse
import threading
from dotenv import load_dotenv
from werkzeug.security import generate_password_hash, check_password_hash

# ================= INIT =================
app = Flask(__name__)
load_dotenv()

app.secret_key = os.getenv("SECRET_KEY", "dev_secret")

# ================= MAIL =================
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = os.getenv("MAIL_USERNAME")
app.config['MAIL_PASSWORD'] = os.getenv("MAIL_PASSWORD")

# ✅ FIX IMPORTANT
app.config['MAIL_DEFAULT_SENDER'] = app.config['MAIL_USERNAME']

mail = Mail(app)

otp_store = {}

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
    return render_template("login.html")

# ================= FORGOT PASSWORD =================
@app.route("/forgot_password")
def forgot_password():
    return render_template("forgot_password.html")
# ================= REGISTER =================
@app.route("/create_teacher_account")
def create_teacher_account():
    return render_template("register.html")

#================== SAVE REGISTER =================
@app.route("/save_register", methods=["POST"])
def save_register():
    fullname = request.form["fullname"]
    username = request.form["username"].strip().lower()
    password = generate_password_hash(request.form["password"])
    subject = request.form["subject"]
    email = request.form["email"]

    db = get_db()
    cursor = db.cursor()

    cursor.execute("SELECT * FROM teachers WHERE username=%s", (username,))
    if cursor.fetchone():
        db.close()
        return render_template("register.html", msg="Username exists ❌")

    cursor.execute("""
        INSERT INTO teachers(full_name, username, password, subject, email)
        VALUES (%s,%s,%s,%s,%s)
    """, (fullname, username, password, subject, email))

    db.commit()
    db.close()

    return render_template("register.html", success="Account created ✅")


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

    # check user exists
    if not user:
        return "User not found ❌"

    # RULE: password must start with 4
    if not password.startswith("4"):
        return "Password must start with 4 ❌"

    # check password hash
    if check_password_hash(user["password"], password):

        session["username"] = username
        session["role"] = user.get("role", "teacher")

        if session["role"] == "admin":
            return redirect("/admin")
        else:
            return redirect("/dashboard")

    return "Password mismatch ❌"
    #================= ADMIN =================
@app.route("/admin")
def admin():
    if "username" not in session:
        return redirect("/")

    if session.get("role") != "admin":
        return "Access denied ❌"

    db = get_db()
    cursor = db.cursor()

    # teachers list
    cursor.execute("SELECT * FROM teachers")
    teachers = cursor.fetchall()

    # attendance records
    cursor.execute("""
        SELECT teacher_name, subject, checkin_time, status
        FROM attendance
        ORDER BY checkin_time DESC
    """)
    attendance = cursor.fetchall()

    db.close()

    return render_template(
        "admin.html",
        teachers=teachers,
        attendance=attendance
    )
    #========= DASHBOARD =================
@app.route("/dashboard")
def dashboard():
    if "username" not in session:
        return redirect("/")

    # ADMIN redirect
    if session.get("role") == "admin":
        return redirect("/admin")

    db = get_db()
    cursor = db.cursor()

    cursor.execute("SELECT * FROM teachers WHERE username=%s", (session["username"],))
    user = cursor.fetchone()

    cursor.execute("""
        SELECT teacher_name, subject, checkin_time, status
        FROM attendance
        WHERE DATE(checkin_time)=CURDATE()
        ORDER BY checkin_time DESC
    """)
    records = cursor.fetchall()

    db.close()

    return render_template("dashboard.html", user=user, records=records)

# ================= CHECKIN =================
@app.route("/checkin", methods=["POST"])
def checkin():
    if "username" not in session:
        return redirect("/")

    db = get_db()
    cursor = db.cursor()

    username = session["username"]
    today = datetime.now().date()
    now = datetime.now()

    # check if already checked in today
    cursor.execute("""
        SELECT * FROM attendance
        WHERE username=%s AND DATE(checkin_time)=%s
    """, (username, today))

    if cursor.fetchone():
        session["msg"] = "Already checked in ❌"
        return redirect("/dashboard")

    # get teacher
    cursor.execute("SELECT * FROM teachers WHERE username=%s", (username,))
    teacher = cursor.fetchone()

    # school time
    school_time = datetime.strptime("07:30:00", "%H:%M:%S").time()
    school_dt = datetime.combine(today, school_time)

    # difference in minutes
    diff_minutes = int((now - school_dt).total_seconds() / 60)

    hours = abs(diff_minutes) // 60
    minutes = abs(diff_minutes) % 60

    # status
    if diff_minutes > 0:
        status = f"Late {hours} hrs {minutes} mins"
    else:
        status = f"Early {hours} hrs {minutes} mins"

    # insert attendance
    cursor.execute("""
        INSERT INTO attendance(username, teacher_name, subject, checkin_time, status)
        VALUES (%s,%s,%s,%s,%s)
    """, (username, teacher["full_name"], teacher["subject"], now, status))

    db.commit()
    db.close()

    session["msg"] = f"Check-in successful ✅ {teacher['full_name']}"

    return redirect("/dashboard")
# ================= OTP EMAIL =================
def send_email(app, msg):
    with app.app_context():
        mail.send(msg)


@app.route("/send_code", methods=["POST"])
def send_code():
    email = request.form["email"].strip().lower()

    db = get_db()
    cursor = db.cursor()

    cursor.execute("SELECT * FROM teachers WHERE email=%s", (email,))
    user = cursor.fetchone()
    db.close()

    if not user:
        return "Email not found ❌"

    otp = random.randint(100000, 999999)

    otp_store[email] = {
        "otp": otp,
        "time": datetime.now()
    }

    msg = Message(
        "OTP CODE",
        sender=app.config["MAIL_USERNAME"],
        recipients=[email]
    )

    msg.body = f"Your OTP is {otp} valid 5 minutes"

    threading.Thread(target=send_email, args=(app, msg)).start()

    return render_template("enter_code.html", email=email)


# ================= VERIFY OTP =================
@app.route("/verify_code", methods=["POST"])
def verify_code():
    email = request.form["email"].strip().lower()
    code = request.form["code"].strip()
    new_password = request.form["new_password"]

    data = otp_store.get(email)

    if not data:
        return "Invalid OTP ❌"

    if datetime.now() - data["time"] > timedelta(minutes=5):
        return "OTP expired ❌"

    if str(data["otp"]) != code:
        return "Wrong OTP ❌"

    db = get_db()
    cursor = db.cursor()

    cursor.execute("""
        UPDATE teachers
        SET password=%s
        WHERE email=%s
    """, (generate_password_hash(new_password), email))

    db.commit()
    db.close()

    otp_store.pop(email, None)

    return render_template("reset_success.html")


# ================= LOGOUT =================
@app.route("/logout")
def logout():
    session.pop("username", None)
    return redirect("/")


# ================= RUN =================
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)