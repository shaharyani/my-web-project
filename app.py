from flask import Flask, flash, request, session, redirect, render_template, url_for, make_response, jsonify
from functools import wraps
import pandas as pd
from User import User
from UserManager import UserManager
from datetime import datetime
import logging
from logging.handlers import RotatingFileHandler
import os

app = Flask(__name__)
app.secret_key = '27653sdvft&@gbadhsf7231ah!368'

manager = UserManager(r'C:\Users\shaha\PycharmProjects\PythonProjectWeb\users.xlsx')
manager.load_users_from_excel()  # Load users on startup

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

def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route("/upload_profile_picture", methods=["POST"])
def upload_profile_picture():
    file = request.files.get("profile_picture")

    if not file or file.filename == "":
        flash("לא נבחר קובץ", "error")
        return redirect("/user_page")

    if not allowed_file(file.filename):
        flash("סוג קובץ לא נתמך", "error")
        return redirect("/user_page")

    user = manager.find_user_by_name(session["user_name"])

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
            manager.load_users_from_excel()
            temp_user = manager.find_user_by_name(cookie_user)
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
    return manager.find_user_by_name(user_name)

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
        user=user.get_name(),
        is_admin=user.admin_check(),
        gray_value=0
    )

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        user_name = request.form.get("name").strip()
        user_password = request.form.get("password")
        remember = request.form.get("remember")

        if not user_name or not user_password:
            flash("Please enter both Name and password.", "warning")
            return render_template("login.html")

        manager.load_users_from_excel()
        temp_user = manager.find_user_by_name(user_name)

        if temp_user and temp_user.check_password(user_password):
            session["user_name"] = temp_user.name
            temp_user.is_active = 1  # mark as active
            manager.save_users_to_excel()

            flash(f"שלום {temp_user.name}", "success")
            app.logger.info(f"User '{temp_user.name}' (ID: {temp_user.id}) logged in successfully.")
            response = make_response(redirect("/"))

            if remember == "on":
                response.set_cookie("remember_user", temp_user.name, max_age=60*60*24*30)
            else:
                response.set_cookie("remember_user", '', expires=0)

            return response
        else:
            flash("Invalid Name or password.", "error")
            app.logger.warning(f"User '{temp_user.name}' attempted login with incorrect password.")
            return render_template("login.html")

    return render_template("login.html")

@app.route("/logout")
def logout():
    user = get_current_user()
    if user:
        user.is_active = 0
        user.set_last_login(datetime.now().strftime("%H:%M %d/%m/%Y"))
        manager.save_users_to_excel()  # save the change

    session.clear()
    response = make_response(redirect("/login"))
    response.delete_cookie("remember_user")
    flash("You have been logged out.", "success")
    app.logger.info(f"User '{user.name}' (ID: {user.id}) logged out successfully.")
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
    if not user or not user.is_admin:
        flash('למשתמש זה אין הרשאות מנהל.', "error")
        return redirect(url_for('home'))

    manager.load_users_from_excel()
    return render_template('admin.html', user=user.get_name(), users=manager.users)

@app.route('/create_user', methods=['POST'])
@login_required
def create_user():
    current_user = get_current_user()

    if not current_user.is_admin:
        flash("You are not authorized to create users.", "error")
        return redirect(url_for('admin'))

    # Get form data
    name = request.form['name']
    mador = request.form['mador']
    password = request.form['password']
    is_active = request.form.get('is_active') == 'on'
    is_admin = request.form.get('is_admin') == 'on'
    last_login = datetime.now().strftime("%H:%M %d/%m/%Y")

    # Determine type based on admin status
    if is_admin:
        type = 2  # Admin
    else:
        type = int(request.form['type'])  # Keep the type from the form

    # Check if name is unique
    if manager.find_user_by_name(name):
        flash(f"Username '{name}' already exists. Please choose a different name.", "error")
        return redirect(url_for('admin'))

    # Generate unique ID
    if manager.users:
        max_id = max([u.id for u in manager.users])
        new_id = max_id + 1
    else:
        new_id = 1

    # Add user (no Excel reload here!)
    new_user = User(name, mador, new_id, password, type, is_active, is_admin, last_login)
    manager.add_user(new_user)

    flash(f"User {name} created successfully with ID {new_id}.", "success")
    return redirect(url_for('admin'))

@app.route("/edit_user", methods=["POST"])
@login_required
def edit_user():
    current_user = get_current_user()
    if not current_user.is_admin:
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

    user = manager.find_user_by_name(name)
    if not user:
        flash("משתמש לא נמצא", "error")
        return redirect(url_for("admin"))

    user.mador = mador
    user.type = 2 if is_admin else user_type
    user.is_admin = is_admin

    manager.save_users_to_excel()

    flash("המשתמש עודכן בהצלחה", "success")
    app.logger.info(
        f"User '{user.name}' (ID: {user.id}) status changed to {user.type} by admin."
    )

    return redirect(url_for("admin"))

@app.route("/change_password", methods=["POST"])
def change_password():
    current = request.form.get("current_password")
    new = request.form.get("new_password")
    confirm = request.form.get("confirm_password")

    user = manager.find_user_by_name(session.get("user_name"))

    # Check current password
    if not user.check_password(current):
        flash("סיסמה נוכחית שגויה", "error")
        return redirect("/user_page")

    # Check new password matches confirm
    if new != confirm:
        flash("הסיסמא החדשה אינה תואמת", "error")
        return redirect("/user_page")

    # Update user object
    user.password = new  # TODO: replace with hashed password if needed
    flash("סיסמה עודכנה בהצלחה", "success")
    app.logger.info(f"User '{user.name}' (ID: {user.id}) changed password.")

    # --- Update Excel file ---
    try:
        # Load Excel file
        df = pd.read_excel(manager.excel_file)

        # Find row by user name
        user_row = df['name'] == user.name

        # Update password column
        df.loc[user_row, 'password'] = new  # TODO: hash if required

        # Save Excel file
        df.to_excel(manager.excel_file, index=False)
    except Exception as e:
        flash(f"שגיאה בעדכון הקובץ: {e}", "error")

    return redirect("/user_page")

@app.route('/delete_user/<username>', methods=['POST'])
@login_required
def delete_user(username):
    current_user = get_current_user()
    if not current_user.is_admin:
        flash("You are not authorized to delete users.", "error")
        return redirect(url_for('admin'))

    if username == current_user.name:
        flash("You cannot delete your own account.", "error")
        return redirect(url_for('admin'))

    manager.remove_user(username)
    flash(f"User {username} has been deleted.", "success")
    return redirect(url_for('admin'))

@app.route("/admin")
@login_required
def admin_dashboard():
    current_user = get_current_user()
    if not current_user or not current_user.is_admin:
        flash("למשתמש זה אין הרשאות מנהל.", "error")
        return redirect(url_for("home"))

    manager.load_users_from_excel()

    # --- Load logs ---
    logs_parsed = []
    if os.path.exists(LOG_FILE):
        with open(LOG_FILE, "r", encoding="utf-8") as f:
            for line in f.readlines()[::-1]:  # newest first
                try:
                    # parse: [timestamp] LEVEL: message
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
        users=manager.users,
        logs=logs_parsed
    )

# ------------------ Other routes (about, user page etc.) ------------------
@app.route('/about')
def about():
    user = get_current_user()
    return render_template('about.html', user=user.get_name() if user else None)

@app.route("/user_page")
@login_required
def user_page():
    user = manager.find_user_by_name(session["user_name"])

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
