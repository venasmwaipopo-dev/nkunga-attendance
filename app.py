from flask import Flask, render_template, request, redirect, session
from datetime import datetime
import mysql.connector
from flask_mail import Mail, Message
import random
import os

# =====================
# FLASK APP INIT
# =====================
app = Flask(__name__)
app.secret_key = "your_secret_key"

# =====================
# EMAIL CONFIG (Flask-Mail)
# =====================
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = os.getenv("MAIL_USERNAME")
app.config['MAIL_PASSWORD'] = os.getenv("MAIL_PASSWORD")

mail = Mail(app)

# =====================
# OTP STORAGE
# =====================
otp_store = {}

# =====================
# DATABASE CONNECTION (RAILWAY)
# =====================
db = mysql.connector.connect(
    host=os.getenv("MYSQLHOST"),
    user=os.getenv("MYSQLUSER"),
    password=os.getenv("MYSQLPASSWORD"),
    database=os.getenv("MYSQLDATABASE"),
    port=int(os.getenv("MYSQLPORT", 3306)),
    auth_plugin='mysql_native_password'
)

cursor = db.cursor(buffered=True)
#
# ================= LOGIN =================
@app.route("/")
def home():
    return render_template("login.html")


@app.route("/login", methods=["POST"])
def login():

    username = request.form["username"]
    password = request.form["password"]

    cursor.execute(
        "SELECT * FROM teachers WHERE username=%s AND password=%s",
        (username, password)
    )

    user = cursor.fetchone()

    if user:
        session["username"] = username
        return redirect("/dashboard")

    return "Wrong username or password ❌"


## ================= REGISTER =================

@app.route("/register")
def register():
    return render_template("register.html")

# ================= SAVE REGISTER =================
@app.route("/save_register", methods=["POST"])
def save_register():

    fullname = request.form["fullname"]
    username = request.form["username"]
    password = request.form["password"]
    subject = request.form["subject"]
    email = request.form["email"]

    # CHECK IF USERNAME EXISTS
    cursor.execute(
        "SELECT * FROM teachers WHERE username=%s",
        (username,)
    )

    existing = cursor.fetchone()

    if existing:
        return "Username already exists ❌"

    # SAVE NEW TEACHER
    cursor.execute("""
        INSERT INTO teachers(full_name, username, password, subject, email)
        VALUES(%s,%s,%s,%s,%s)
    """, (fullname, username, password, subject, email))

    db.commit()

    return """
    <h2 style='color:green;text-align:center;margin-top:50px;'>
        You have registered successfully ✅
    </h2>

    <div style='text-align:center;margin-top:20px;'>
        <a href='/'>
            <button style='padding:10px 20px;font-size:16px;'>
                Login Here
            </button>
        </a>
    </div>
    """
# ================= FORGOT PASSWORD =================
@app.route("/forgot_password")
def forgot_password():
    return render_template("forgot_password.html")
#================= SEND OTP =================
@app.route("/send_code", methods=["POST"])
def send_code():

    email = request.form["email"]

    otp = random.randint(100000, 999999)
    otp_store[email] = otp

    msg = Message(
        "OTP Code",
        sender=app.config['MAIL_USERNAME'],
        recipients=[email]
    )

    msg.body = f"Your OTP code is: {otp}"
    mail.send(msg)

    return render_template("enter_code.html", email=email)
@app.route("/verify_code", methods=["POST"])
def verify_code():

    email = request.form["email"]
    code = request.form["code"]
    new_password = request.form["new_password"]

    if email in otp_store and otp_store[email] == int(code):

        cursor.execute(
            "UPDATE teachers SET password=%s WHERE email=%s",
            (new_password, email)
        )
        db.commit()

        otp_store.pop(email, None)

        return "Password reset successful ✔️"

    return "Invalid OTP ❌"
# ================= DASHBOARD =================
@app.route("/dashboard")
def dashboard():

    if "username" not in session:
        return redirect("/")

    username = session["username"]

    # get teacher info
    cursor.execute("""
        SELECT full_name, subject
        FROM teachers
        WHERE username=%s
    """, (username,))

    user = cursor.fetchone()

    # get attendance records
    cursor.execute("""
        SELECT teacher_name, subject, checkin_time, status
        FROM attendance
        WHERE username=%s
        ORDER BY checkin_time DESC
    """, (username,))

    records = cursor.fetchall()

    return render_template("dashboard.html", user=user, records=records)
# ================= CHECKIN =================
@app.route("/checkin", methods=["POST"])
def checkin():

    username = session["username"]

    today = datetime.now().date()

    # CHECK IF ALREADY CHECKED IN TODAY
    cursor.execute("""
        SELECT * FROM attendance
        WHERE username=%s
        AND DATE(checkin_time)=%s
    """, (username, today))

    existing = cursor.fetchone()

    if existing:
        return """
        <h3 style="color:red;text-align:center;margin-top:50px;">
            You have already checked in today ❌
        </h3>

        <p style="text-align:center;">
            Please come back tomorrow.
        </p>

        <div style="text-align:center;">
            <a href="/dashboard">Go Back</a>
        </div>
        """

    # GET TEACHER INFO
    cursor.execute("""
        SELECT full_name, subject
        FROM teachers
        WHERE username=%s
    """, (username,))

    teacher = cursor.fetchone()

    now = datetime.now()

    school_time = datetime.strptime("07:30:00", "%H:%M:%S")
    current_time = datetime.strptime(now.strftime("%H:%M:%S"), "%H:%M:%S")

    diff = int((school_time - current_time).total_seconds() / 60)

    if diff >= 0:
        status = f"Earlier for {diff} mins"
    else:
        status = f"Late for {abs(diff)} mins"

    # INSERT ATTENDANCE
    cursor.execute("""
        INSERT INTO attendance
        (username, teacher_name, subject, checkin_time, status)
        VALUES (%s,%s,%s,%s,%s)
    """, (username, teacher[0], teacher[1], now, status))

    db.commit()

    return """
    <h3 style="color:green;text-align:center;margin-top:50px;">
        Check-in successful ✅
    </h3>

    <p style="text-align:center;">
        Status saved successfully
    </p>

    <div style="text-align:center;">
        <a href="/dashboard">Go Back</a>
    </div>
    """
# ================= LOGOUT =================
@app.route("/logout")
def logout():
    session.pop("username", None)
    return redirect("/")
  
def get_user(username):
    cursor.execute("SELECT * FROM teachers WHERE username=%s", (username,))
    return cursor.fetchone()

# ================= GET RECORDS =================
def get_records():
    cursor.execute("""
        SELECT t.full_name, t.subject, a.checkin_time, a.status
        FROM attendance a
        JOIN teachers t ON a.username = t.username
        WHERE DATE(a.checkin_time)=CURDATE()
        ORDER BY a.checkin_time DESC
    """)
    return cursor.fetchall()

def get_records():
    cursor.execute("""
        SELECT t.full_name, t.subject, a.checkin_time, a.status
        FROM attendance a
        JOIN teachers t ON a.username = t.username
        WHERE DATE(a.checkin_time)=CURDATE()
        ORDER BY a.checkin_time DESC
    """)
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
from flask import Flask, render_template, request, redirect, session
from datetime import datetime
import mysql.connector
from flask_mail import Mail, Message
import random

app = Flask(__name__)
app.secret_key = "your_secret_key"

# EMAIL
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = 'venasmwaipopo@gmail.com'
app.config['MAIL_PASSWORD'] = 'udbj zgsv vues juyy'

mail = Mail(app)

otp_store = {}
# DATABASE
db = mysql.connector.connect(
    host=os.getenv("MYSQLHOST"),
    user=os.getenv("MYSQLUSER"),
    password=os.getenv("MYSQLPASSWORD"),
    database=os.getenv("MYSQLDATABASE"),
    port=int(os.getenv("MYSQLPORT", 3306))
)

cursor = db.cursor(buffered=True)


#
# ================= LOGIN =================
@app.route("/")
def home():
    return render_template("login.html")


@app.route("/login", methods=["POST"])
def login():

    username = request.form["username"]
    password = request.form["password"]

    cursor.execute(
        "SELECT * FROM teachers WHERE username=%s AND password=%s",
        (username, password)
    )

    user = cursor.fetchone()

    if user:
        session["username"] = username
        return redirect("/dashboard")

    return "Wrong username or password ❌"


## ================= REGISTER =================

@app.route("/register")
def register():
    return render_template("register.html")

# ================= SAVE REGISTER =================
@app.route("/save_register", methods=["POST"])
def save_register():

    fullname = request.form["fullname"]
    username = request.form["username"]
    password = request.form["password"]
    subject = request.form["subject"]
    email = request.form["email"]

    # CHECK IF USERNAME EXISTS
    cursor.execute(
        "SELECT * FROM teachers WHERE username=%s",
        (username,)
    )

    existing = cursor.fetchone()

    if existing:
        return "Username already exists ❌"

    # SAVE NEW TEACHER
    cursor.execute("""
        INSERT INTO teachers(full_name, username, password, subject, email)
        VALUES(%s,%s,%s,%s,%s)
    """, (fullname, username, password, subject, email))

    db.commit()

    return """
    <h2 style='color:green;text-align:center;margin-top:50px;'>
        You have registered successfully ✅
    </h2>

    <div style='text-align:center;margin-top:20px;'>
        <a href='/'>
            <button style='padding:10px 20px;font-size:16px;'>
                Login Here
            </button>
        </a>
    </div>
    """
# ================= FORGOT PASSWORD =================
@app.route("/forgot_password")
def forgot_password():
    return render_template("forgot_password.html")
#================= SEND OTP =================
@app.route("/send_code", methods=["POST"])
def send_code():

    email = request.form["email"]

    otp = random.randint(100000, 999999)
    otp_store[email] = otp

    msg = Message(
        "OTP Code",
        sender=app.config['MAIL_USERNAME'],
        recipients=[email]
    )

    msg.body = f"Your OTP code is: {otp}"
    mail.send(msg)

    return render_template("enter_code.html", email=email)
@app.route("/verify_code", methods=["POST"])
def verify_code():

    email = request.form["email"]
    code = request.form["code"]
    new_password = request.form["new_password"]

    if email in otp_store and otp_store[email] == int(code):

        cursor.execute(
            "UPDATE teachers SET password=%s WHERE email=%s",
            (new_password, email)
        )
        db.commit()

        otp_store.pop(email, None)

        return "Password reset successful ✔️"

    return "Invalid OTP ❌"
# ================= DASHBOARD =================
@app.route('/dashboard')
def dashboard():
    records = get_records()
    return render_template("dashboard.html", records=records)

    username = session["username"]

    # get teacher info
    cursor.execute("""
        SELECT full_name, subject
        FROM teachers
        WHERE username=%s
    """, (username,))

    user = cursor.fetchone()

    # get attendance records
    cursor.execute("""
        SELECT teacher_name, subject, checkin_time, status
        FROM attendance
        WHERE username=%s
        ORDER BY checkin_time DESC
    """, (username,))

    records = cursor.fetchall()

    return render_template("dashboard.html", user=user, records=records)
# ================= CHECKIN =================
@app.route("/checkin", methods=["POST"])
def checkin():

    username = session["username"]

    today = datetime.now().date()

    # CHECK IF ALREADY CHECKED IN TODAY
    cursor.execute("""
        SELECT * FROM attendance
        WHERE username=%s
        AND DATE(checkin_time)=%s
    """, (username, today))

    existing = cursor.fetchone()

    if existing:
        return """
        <h3 style="color:red;text-align:center;margin-top:50px;">
            You have already checked in today ❌
        </h3>

        <p style="text-align:center;">
            Please come back tomorrow.
        </p>

        <div style="text-align:center;">
            <a href="/dashboard">Go Back</a>
        </div>
        """

    # GET TEACHER INFO
    cursor.execute("""
        SELECT full_name, subject
        FROM teachers
        WHERE username=%s
    """, (username,))

    teacher = cursor.fetchone()

    now = datetime.now()

    school_time = datetime.strptime("07:30:00", "%H:%M:%S")
    current_time = datetime.strptime(now.strftime("%H:%M:%S"), "%H:%M:%S")

    diff = int((school_time - current_time).total_seconds() / 60)

    if diff >= 0:
        status = f"Earlier for {diff} mins"
    else:
        status = f"Late for {abs(diff)} mins"

    # INSERT ATTENDANCE
    cursor.execute("""
        INSERT INTO attendance
        (username, teacher_name, subject, checkin_time, status)
        VALUES (%s,%s,%s,%s,%s)
    """, (username, teacher[0], teacher[1], now, status))

    db.commit()

    return """
    <h3 style="color:green;text-align:center;margin-top:50px;">
        Check-in successful ✅
    </h3>

    <p style="text-align:center;">
        Status saved successfully
    </p>

    <div style="text-align:center;">
        <a href="/dashboard">Go Back</a>
    </div>
    """
# ================= LOGOUT =================
@app.route("/logout")
def logout():
    session.pop("username", None)
    return redirect("/")
  
def get_user(username):
    cursor.execute("SELECT * FROM teachers WHERE username=%s", (username,))
    return cursor.fetchone()

# ================= GET RECORDS =================
def get_records():
    cursor.execute("""
        SELECT t.full_name, t.subject, a.checkin_time, a.status
        FROM attendance a
        JOIN teachers t ON a.username = t.username
        WHERE DATE(a.checkin_time)=CURDATE()
        ORDER BY a.checkin_time DESC
    """)
    return cursor.fetchall()


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)