from flask import Flask, render_template, request, redirect, session
from datetime import datetime, timedelta
import pymysql
from flask_mail import Mail, Message
import random
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

# ================= MAIL =================
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = os.getenv("MAIL_USERNAME")
app.config['MAIL_PASSWORD'] = os.getenv("MAIL_PASSWORD")

mail = Mail(app)

otp_store = {}

# ================= HOME =================
@app.route("/")
def home():
    return render_template("login.html")

# ================= REGISTER PAGE =================
@app.route("/create_teacher_account")
def create_teacher_account():
    return render_template("register.html")

# ================= REGISTER SAVE (FIXED) =================
@app.route("/save_register", methods=["POST"])
def save_register():
    try:
        fullname = request.form["fullname"]
        username = request.form["username"].strip().lower()
        password = generate_password_hash(request.form["password"])
        subject = request.form["subject"]
        email = request.form["email"]

        db = get_db()
        cursor = db.cursor()

        # Check username
        cursor.execute(
            "SELECT * FROM teachers WHERE username=%s",
            (username,)
        )
        existing = cursor.fetchone()

        if existing:
            db.close()
            return render_template(
                "register.html",
                msg="Username already exists ❌"
            )

        # Save teacher
        cursor.execute("""
            INSERT INTO teachers
            (full_name, username, password, subject, email)
            VALUES (%s,%s,%s,%s,%s)
        """, (fullname, username, password, subject, email))

        db.commit()
        db.close()

        return render_template(
            "register.html",
            success="Account created successfully ✅"
        )

    except Exception as e:
        print("REGISTER ERROR:", e)
        return render_template(
            "register.html",
            msg=f"Error: {e}"
        )
        #================== LOGIN =================
@app.route("/login", methods=["POST"])
def login():
    db = get_db()
    cursor = db.cursor()

    username = request.form["username"].strip().lower()
    password = request.form["password"]

    cursor.execute("SELECT * FROM teachers WHERE username=%s", (username,))
    user = cursor.fetchone()

    db.close()

    # user check
    if not user:
        return "User not found ❌"

    # password check (IMPORTANT FIX)
    if check_password_hash(user["password"], password):
        session["username"] = username
        return redirect("/dashboard")

    return "Password mismatch ❌"
# ================= DASHBOARD =================
@app.route("/dashboard")
def dashboard():
    if "username" not in session:
        return redirect("/")

    db = get_db()
    cursor = db.cursor()

    # get user info
    cursor.execute(
        "SELECT * FROM teachers WHERE username=%s",
        (session["username"],)
    )
    user = cursor.fetchone()

    # get attendance records
    cursor.execute("""
        SELECT teacher_name, subject, checkin_time, status
        FROM attendance
        ORDER BY checkin_time DESC
    """)
    records = cursor.fetchall()

    # check if already checked in today
    cursor.execute("""
        SELECT * FROM attendance
        WHERE username=%s AND DATE(checkin_time)=CURDATE()
    """, (session["username"],))

    today_checkin = cursor.fetchone()

    db.close()

    return render_template(
        "dashboard.html",
        user=user,
        records=records,
        msg=session.pop("msg", None),
        checked=today_checkin
    )
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

    # 🔥 CHECK IF ALREADY CHECKED IN TODAY
    cursor.execute("""
        SELECT * FROM attendance
        WHERE username=%s AND DATE(checkin_time)=%s
    """, (username, today))

    already = cursor.fetchone()

    if already:
        session["msg"] = "You already checked in today ❌"
        return redirect("/dashboard")

    # get teacher
    cursor.execute("SELECT * FROM teachers WHERE username=%s", (username,))
    teacher = cursor.fetchone()

    school_time = datetime.strptime("07:30:00", "%H:%M:%S").time()
    school_dt = datetime.combine(today, school_time)

    diff = int((now - school_dt).total_seconds() / 60)
    status = f"Late {diff} mins" if diff > 0 else f"Early {abs(diff)} mins"

    # insert attendance
    cursor.execute("""
        INSERT INTO attendance(username, teacher_name, subject, checkin_time, status)
        VALUES (%s,%s,%s,%s,%s)
    """, (username, teacher["full_name"], teacher["subject"], now, status))

    db.commit()
    db.close()

    session["msg"] = f"Check-in successful ✅ ({teacher['full_name']})"

    return redirect("/dashboard")
# ================= FORGOT PASSWORD =================
@app.route("/forgot_password")
def forgot_password():
    return render_template("forgot_password.html")


@app.route("/send_code", methods=["POST"])
def send_code():
    email = request.form["email"]

    otp = random.randint(100000, 999999)
    otp_store[email] = {"otp": otp, "time": datetime.now()}

    print("OTP FOR DEBUG:", otp)  # unaweza kuona Render logs

    return render_template("enter_code.html", email=email)
# ================= VERIFY OTP =================
@app.route("/verify_code", methods=["POST"])
def verify_code():
    email = request.form["email"]
    code = int(request.form["code"])
    new_password = request.form["new_password"]

    data = otp_store.get(email)

    if not data:
        return "Invalid OTP ❌"

    if datetime.now() - data["time"] > timedelta(minutes=5):
        return "OTP expired ❌"

    if data["otp"] == code:
        db = get_db()
        cursor = db.cursor()

        cursor.execute("""
            UPDATE teachers
            SET password=%s
            WHERE email=%s
        """, (generate_password_hash(new_password), email))

        db.commit()
        db.close()

        otp_store.pop(email)

        return redirect("/")

    return "Wrong OTP ❌"

    try:
        msg = Message(
            "OTP Code",
            sender=app.config["MAIL_USERNAME"],
            recipients=[email]
        )
        msg.body = f"Your OTP is: {otp}"
        mail.send(msg)

    except Exception as e:
        print("EMAIL ERROR:", e)

    return render_template("enter_code.html", email=email)
# ================= LOGOUT =================
@app.route("/logout")
def logout():
    session.pop("username", None)
    return redirect("/")

# ================= RUN =================
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)