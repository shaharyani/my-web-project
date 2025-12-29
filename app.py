from flask import Flask, flash, request, session, redirect, render_template, url_for, make_response
from functools import wraps
from flask_login import login_required
import re
from User import User
from datetime import datetime
import logging
from logging.handlers import RotatingFileHandler
from db import get_users_db
from db import get_products_db
import os

app = Flask(__name__)
app.secret_key = '27653sdvft&@gbadhsf7231ah!368'

conn = get_users_db()
cursor = conn.cursor()
cursor.execute("""
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT UNIQUE NOT NULL,
    mador TEXT,
    password TEXT NOT NULL,
    type INTEGER DEFAULT 2,
    is_active INTEGER DEFAULT 1,
    is_admin INTEGER DEFAULT 0,
    last_login TEXT,
    profile_image TEXT DEFAULT 'user_photo.png'
)
""")
conn.commit()
conn.close()

conn = get_products_db()
cursor = conn.cursor()

cursor.execute("""
    CREATE TABLE IF NOT EXISTS products (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        serial TEXT UNIQUE NOT NULL,
        code TEXT UNIQUE NOT NULL,
        card_type TEXT NOT NULL,
        land_type TEXT NOT NULL,
        status TEXT DEFAULT 'N',   -- R - RED | B - BLACK | W - WHITE | N - NONE
        owner TEXT,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    )
""")
conn.commit()
conn.close()


UPLOAD_FOLDER = os.path.join("static", "profile_pics")
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "gif"}

# Ensure logs folder exists
os.makedirs("logs", exist_ok=True)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_FILE = os.path.join(BASE_DIR, "logs", "app.log")

# Create logs folder if it doesn't exist
if not os.path.exists('logs'):
    os.mkdir('logs')

# Create a rotating file handler
handler = RotatingFileHandler(
    LOG_FILE,
    maxBytes=1_000_000,  # 1 MB per file
    backupCount=5,        # keep up to 5 old log files
    encoding="utf-8"
)

# Log format: [timestamp] LEVEL: message
formatter = logging.Formatter("[%(asctime)s] %(levelname)s: %(message)s")
handler.setFormatter(formatter)
handler.setLevel(logging.INFO)  # log INFO and above to file

# Attach handler to Flask's built-in logger
app.logger.addHandler(handler)
app.logger.setLevel(logging.INFO)  # set minimum level for the app logger

# Optional: also log to console for debugging
console_handler = logging.StreamHandler()
console_handler.setFormatter(formatter)
console_handler.setLevel(logging.INFO)
app.logger.addHandler(console_handler)

def get_logs(limit=5):
    logs = []
    if os.path.exists(LOG_FILE):
        with open(LOG_FILE, "r", encoding="utf-8") as f:
            for line in f.readlines():
                # Parse each line like: [timestamp] LEVEL: message
                match = re.match(r"\[(.*?)\] (\w+): (.*)", line)
                if match:
                    timestamp, level, message = match.groups()
                    logs.append({
                        "timestamp": timestamp,
                        "level": level,
                        "message": message
                    })
    return logs[-limit:]

def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route("/upload_profile_picture", methods=["POST"])
@login_required
def upload_profile_picture():
    file = request.files.get("profile_picture")

    if not file or file.filename == "":
        flash("לא נבחר קובץ", "error")
        return redirect("/user_page")

    if not allowed_file(file.filename):
        flash("סוג קובץ לא נתמך", "error")
        return redirect("/user_page")

    user = User.get_by_name(session.get("user_name"))

    ext = file.filename.rsplit(".", 1)[1].lower()
    filename = f"user_{user.id}.{ext}"
    filepath = os.path.join(app.config["UPLOAD_FOLDER"], filename)

    file.save(filepath)

    flash("התמונה עודכנה בהצלחה", "success")
    return redirect("/user_page")

@app.before_request
def load_user_from_cookie():
    if "user_name" not in session:
        cookie_user = request.cookies.get("remember_user")
        if cookie_user:
            # Load the user directly from DB
            temp_user = User.get_by_name(cookie_user)
            if temp_user:
                session["user_name"] = temp_user.get_name()

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_name' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def get_current_user():
    """Return the current logged-in user object or None."""
    user_name = session.get("user_name")
    if not user_name:
        return None
    return User.get_by_name(user_name)

# ------------------ Routes ------------------
@app.route('/')
@login_required
def home():
    user = get_current_user()
    gitLab_logo = "images/gitLab_logo.png"  # static path, no leading slash
    user_photo = "images/user_photo.png"    # default

    # Check if user has uploaded a profile picture
    for ext in ["png", "jpg", "jpeg", "gif"]:
        path = f"static/profile_pics/user_{user.id}.{ext}"
        if os.path.exists(path):
            user_photo = f"profile_pics/user_{user.id}.{ext}"  # path relative to static/
            break

    return render_template(
        'index.html',
        user=user.get_name() if user else None,
        gitLab_logo=gitLab_logo,
        user_photo=user_photo
    )

@app.route('/card<int:num>')
@login_required
def card(num):
    user = get_current_user()
    if not user:
        flash("User not found.", "error")
        return redirect(url_for('login'))

    return render_template(
        f'card{num}.html',
        user=user.get_by_name(user.get_name()) if user else None,
        is_admin=user.admin_check(),
        gray_value=0
    )

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        user_name = request.form.get("name", "").strip()
        user_password = request.form.get("password")
        remember = request.form.get("remember")

        if not user_name or not user_password:
            flash("Please enter both Name and password.", "warning")
            return render_template("login.html")

        temp_user = User.get_by_name(user_name)

        if temp_user and temp_user.check_password(user_password):
            session["user_name"] = temp_user.name
            temp_user.activate()  # mark as active

            flash(f"שלום {temp_user.name}", "success")
            app.logger.info(f"User '{temp_user.name}' (ID: {temp_user.id}) logged in successfully.")
            response = make_response(redirect("/"))

            if remember == "on":
                response.set_cookie("remember_user", temp_user.name, max_age=60 * 60 * 24 * 30)
            else:
                response.set_cookie("remember_user", '', expires=0)

            return response
        else:
            flash("Invalid Name or password.", "error")
            app.logger.warning(f"Login failed for '{user_name}'.")
            return render_template("login.html")

    # Ensure GET request returns the login page
    return render_template("login.html")

@app.route("/logout")
def logout():
    user = User.get_by_name(session.get("user_name"))
    if user:
        user.deactivate()
        user.set_last_login(datetime.now().strftime("%H:%M %d/%m/%Y"))

    session.clear()
    response = make_response(redirect("/login"))
    response.delete_cookie("remember_user")
    flash("You have been logged out.", "success")
    app.logger.info(f"User '{user.name}' logged out successfully." if user else "Unknown user logged out.")
    return response

@app.route("/view-result/<serial>/<code>/<world>/<land>")
@login_required
def view_result(serial, code, world, land):
    # If you want additional info, you can prepare it here
    info_text = f"מידע מפורט על {serial} ({code})"
    return render_template(
        "view-result.html",
        serial=serial,
        code=code,
        world=world,
        land=land,
        info_text=info_text
    )

# ------------------ Admin Routes ------------------
@app.route('/admin')
@login_required
def admin():
    user = get_current_user()
    logs = get_logs(limit=5)
    if not user or not user.is_admin:
        flash("למשתמש זה אין הרשאות מנהל.", "error")
        return redirect(url_for("home"))

    # Fetch all users from the database
    conn = get_users_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users ORDER BY id")
    users_data = cursor.fetchall()
    conn.close()

    # Convert DB rows to User objects
    users = []
    for row in users_data:
        u = User(
            name=row[1],
            mador=row[2],
            id=row[0],
            password=row[3],
            type=row[4],
            is_active=bool(row[5]),
            is_admin=bool(row[6]),
            last_login=row[7],
            profile_image=row[8] if row[8] else "user_photo.png"
        )
        users.append(u)

    return render_template('admin.html', user=user.get_name(), users=users, logs=logs)

@app.route('/create_user', methods=['POST'])
@login_required
def create_user():
    current_user = User.get_by_name(session["user_name"])

    if not current_user.is_admin:
        flash("You are not authorized to create users.", "error")
        return redirect(url_for('admin_dashboard'))

    name = request.form['name']
    mador = request.form['mador']
    password = request.form['password']
    is_active = request.form.get('is_active') == 'on'
    type = int(request.form['type'])
    is_admin = True if type == 0 else False

    if User.get_by_name(name):
        flash(f"Username '{name}' already exists.", "error")
        return redirect(url_for('admin_dashboard'))

    last_login = datetime.now().strftime("%H:%M %d/%m/%Y")
    new_user = User.create(name, mador, password, type, is_active, is_admin, last_login)

    flash(f"User {name} created successfully with ID {new_user.id}.", "success")
    return redirect(url_for('admin_dashboard'))

@app.route("/edit_user", methods=["POST"])
@login_required
def edit_user():
    current_user = User.get_by_name(session.get("user_name"))
    if not current_user or not current_user.is_admin:
        flash("אין הרשאה", "error")
        return redirect(url_for("admin"))

    name = request.form.get("name")
    mador = request.form.get("mador")
    is_admin = "is_admin" in request.form

    # Safely get type
    user_type = request.form.get("type")
    try:
        user_type = int(user_type)
    except (ValueError, TypeError):
        user_type = 0  # default type if missing

    user = User.get_by_name(name)
    if not user:
        flash("משתמש לא נמצא", "error")
        return redirect(url_for("admin"))

    # Update fields
    user.mador = mador
    user.type = 2 if is_admin else user_type
    user.is_admin = is_admin

    # Update DB fields
    user.update_db_field("mador", user.mador)
    user.update_db_field("type", user.type)
    user.update_db_field("is_admin", int(user.is_admin))

    flash("המשתמש עודכן בהצלחה", "success")
    app.logger.info(
        f"User '{user.name}' (ID: {user.id}) updated: type={user.type}, admin={user.is_admin} by {current_user.name}."
    )

    return redirect(url_for("admin"))

@app.route("/change_password", methods=["POST"])
def change_password():
    current = request.form.get("current_password")
    new = request.form.get("new_password")
    confirm = request.form.get("confirm_password")

    user = User.get_by_name(session.get("user_name"))

    if not user.check_password(current):
        flash("סיסמה נוכחית שגויה", "error")
        return redirect("/user_page")

    if new != confirm:
        flash("הסיסמא החדשה אינה תואמת", "error")
        return redirect("/user_page")

    user.set_password(new)  # hashes & updates DB automatically

    flash("סיסמה עודכנה בהצלחה", "success")
    app.logger.info(f"User '{user.name}' (ID: {user.id}) changed password.")

    return redirect("/user_page")

@app.route('/delete_user/<username>', methods=['POST'])
@login_required
def delete_user(username):
    current_user = User.get_by_name(session["user_name"])
    if not current_user.is_admin:
        flash("You are not authorized to delete users.", "error")
        return redirect(url_for('admin_dashboard'))

    if username == current_user.name:
        flash("You cannot delete your own account.", "error")
        return redirect(url_for('admin_dashboard'))

    user_to_delete = User.get_by_name(username)
    if user_to_delete:
        conn = get_users_db()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM users WHERE id=?", (user_to_delete.id,))
        conn.commit()
        conn.close()
        flash(f"User {username} has been deleted.", "success")
    else:
        flash(f"User {username} not found.", "error")

    return redirect(url_for('admin_dashboard'))

@app.route("/admin")
@login_required
def admin_dashboard():
    current_user = get_current_user()
    if not current_user or not current_user.is_admin:
        flash("למשתמש זה אין הרשאות מנהל.", "error")
        return redirect(url_for("home"))

    # --- Load users from DB ---
    conn = get_users_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users ORDER BY id")
    users_data = cursor.fetchall()
    conn.close()

    users = []
    for row in users_data:
        u = User(
            name=row[1],
            mador=row[2],
            id=row[0],
            password=row[3],
            type=row[4],
            is_active=bool(row[5]),
            is_admin=bool(row[6]),
            last_login=row[7],
            profile_image=row[8] if row[8] else "user_photo.png"
        )
        users.append(u)

    # --- Load logs ---
    logs_parsed = []
    if os.path.exists(LOG_FILE):
        with open(LOG_FILE, "r", encoding="utf-8") as f:
            for line in f.readlines()[::-1]:  # newest first
                try:
                    timestamp_end = line.index("]") + 1
                    timestamp = line[:timestamp_end].strip()
                    rest = line[timestamp_end:].strip()
                    level_end = rest.index(":")
                    level = rest[:level_end].strip()
                    message = rest[level_end + 1:].strip()
                    logs_parsed.append({
                        "timestamp": timestamp,
                        "level": level,
                        "message": message
                    })
                except Exception:
                    logs_parsed.append({"timestamp": "", "level": "", "message": line.strip()})

    return render_template(
        "admin.html",
        user=current_user.get_name(),
        users=users,
        logs=logs_parsed
    )

lands = ["ארץ 1", "ארץ 2", "ארץ 3", "ארץ 4", "ארץ 5"]
@app.route('/card<int:num>' , methods=["POST"])
@login_required
def add_land(): #TODO: Finish this process
    user = get_current_user()
    num = request.form.get("num") # The number of the card that came from

    land_name = request.form.get("land_name", "").strip()

    if not land_name:
        flash("שם הארץ לא יכול להיות ריק", "error")

    if land_name in lands:
        flash("הארץ כבר קיימת", "error")


    lands.append(land_name)
    flash("ארץ נוספה בהצלחה", "success")

    return render_template(
        f'card{num}.html',
        user=user.get_name(),
        is_admin=user.admin_check(),
        gray_value=0
    )

# ------------------ Other routes (about, user page etc.) ------------------
@app.route('/about')
def about():
    user = get_current_user()
    return render_template('about.html', user=user.get_name() if user else None)

@app.route("/user_page")
@login_required
def user_page():
    user = User.get_by_name(session.get("user_name"))
    # Profile image logic
    profile_image = "images/user_photo.png"
    for ext in ["png", "jpg", "jpeg", "gif"]:
        path = f"static/profile_pics/user_{user.id}.{ext}"
        if os.path.exists(path):
            profile_image = path.replace("static/", "")
            break

    return render_template(
        "user-page.html",
        user=user,
        profile_image=profile_image
    )

# ------------------ Run App ------------------
if __name__ == "__main__":
    app.run(debug=True)
