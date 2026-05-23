from flask import Flask, render_template, request, redirect, session
from datetime import datetime
import mysql.connector
from flask_mail import Mail, Message
import random
import os
import urllib.parse

app = Flask(__name__)
app.secret_key = "your_secret_key"


# ================= EMAIL =================
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = os.getenv("MAIL_USERNAME")
app.config['MAIL_PASSWORD'] = os.getenv("MAIL_PASSWORD")

mail = Mail(app)

otp_store = {}

# ================= ENV CHECK =================
required_envs = ["MYSQLHOST", "MYSQLUSER", "MYSQLPASSWORD", "MYSQLDATABASE"]

missing = [env for env in required_envs if not os.getenv(env)]
if missing:
    print("Missing env variables:", missing)

# ================= DATABASE =================
print("DB URL:", os.getenv("MYSQL_PUBLIC_URL"))
db_url = os.getenv("MYSQL_PUBLIC_URL")

# kama umeweka variable jina tofauti, tumia fallback hii pia
if not db_url:
    db_url = os.getenv("MYSQL_URL")

if not db_url:
    raise Exception("Missing MYSQL connection URL")

url = urllib.parse.urlparse(db_url)

db = mysql.connector.connect(
    host=url.hostname,
    user=url.username,
    password=url.password,
    database=url.path.lstrip("/"),
    port=url.port
)

cursor = db.cursor(buffered=True)
# ================= HOME =================
@app.route("/")
def home():
    return render_template("login.html")

# ================= LOGIN =================
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

# ================= REGISTER =================
@app.route("/register")
def register():
    return render_template("register.html")

@app.route("/save_register", methods=["POST"])
def save_register():
    fullname = request.form["fullname"]
    username = request.form["username"]
    password = request.form["password"]
    subject = request.form["subject"]
    email = request.form["email"]

    cursor.execute("SELECT * FROM teachers WHERE username=%s", (username,))
    if cursor.fetchone():
        return "Username already exists ❌"

    cursor.execute("""
        INSERT INTO teachers(full_name, username, password, subject, email)
        VALUES(%s,%s,%s,%s,%s)
    """, (fullname, username, password, subject, email))

    db.commit()

    return "Registered successfully ✅"

# ================= FORGOT PASSWORD =================
@app.route("/forgot_password")
def forgot_password():
    return render_template("forgot_password.html")

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

    cursor.execute("""
        SELECT full_name, subject
        FROM teachers
        WHERE username=%s
    """, (username,))

    user = cursor.fetchone()

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

    if "username" not in session:
        return redirect("/")

    username = session["username"]
    today = datetime.now().date()

    cursor.execute("""
        SELECT * FROM attendance
        WHERE username=%s AND DATE(checkin_time)=%s
    """, (username, today))

    if cursor.fetchone():
        return "Already checked in today ❌"

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

    status = f"Earlier for {diff} mins" if diff >= 0 else f"Late for {abs(diff)} mins"

    cursor.execute("""
        INSERT INTO attendance
        (username, teacher_name, subject, checkin_time, status)
        VALUES (%s,%s,%s,%s,%s)
    """, (username, teacher[0], teacher[1], now, status))

    db.commit()

    return redirect("/dashboard")

# ================= LOGOUT =================
@app.route("/logout")
def logout():
    session.pop("username", None)
    return redirect("/")

# ================= RUN APP =================
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)