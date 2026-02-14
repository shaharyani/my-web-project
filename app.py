import sqlite3

from flask import Flask, session, redirect, render_template, url_for, make_response, send_file, abort, \
    send_from_directory
from functools import wraps
from flask_login import LoginManager
import re
from collections import Counter
from flask import request, jsonify, flash
from Codes import Codes
from Product import Product
from User import User
from datetime import datetime
import logging
from logging.handlers import RotatingFileHandler
from db import get_users_db, get_products_db, get_tests_db, get_codes_db
import os

app = Flask(__name__)
app.secret_key = '27653sdvft&@gbadhsf7231ah!368'
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login"

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

conn1 = get_products_db()
cursor = conn1.cursor()
cursor.execute("""
    CREATE TABLE IF NOT EXISTS products (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        serial TEXT UNIQUE NOT NULL,
        code TEXT NOT NULL,
        land_type TEXT NOT NULL,
        city_name TEXT NOT NULL,
        status TEXT CHECK(status IN ('R','W','B','N')) DEFAULT 'N',
        owner TEXT,
        notes TEXT,          -- רשימת הערות בפורמט JSON
        all_codes TEXT       -- רשימת כל הקודים בפורמט JSON
    )
""")
conn1.commit()
conn1.close()

conn2 = get_tests_db()
cursor = conn2.cursor()
cursor.execute("""
    CREATE TABLE IF NOT EXISTS tests (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        serial TEXT NOT NULL,
        test_name TEXT,              -- העמודה שהייתה חסרה וגרמה לשגיאה
        city_name TEXT,              -- מומלץ: כדי לדעת לאיזו עיר הבדיקה שייכת
        test_level INTEGER NOT NULL,
        checked_by TEXT NOT NULL,
        is_passed INTEGER CHECK(is_passed IN (0, 1)) DEFAULT 0,
        excel_str_file TEXT,
        test_date TEXT,
        is_verified INTEGER CHECK(is_verified IN (0, 1)) DEFAULT 0
    )
""")
conn2.commit()
conn2.close()

conn3 = get_codes_db()
cursor = conn3.cursor()
cursor.execute("""
        CREATE TABLE IF NOT EXISTS city_codes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            city_name TEXT UNIQUE NOT NULL,
            all_codes TEXT NOT NULL
        )
    """)
conn3.commit()
conn3.close()

CITIES_PATH = r"C:\Users\shaha\Desktop\cities"
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

@app.errorhandler(404)
def page_not_found(e):
    return render_template("404.html"), 404

@app.errorhandler(405)
def method_not_supported(e):
    return render_template("405.html"), 404

@app.errorhandler(401)
def page_unauthorized(e):
    return render_template("401.html"), 401

def get_logs(limit=6):
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
@login_manager.user_loader
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

@login_manager.user_loader
def load_user(user_id):
    return User.get_by_id(user_id)

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


def get_product_by_serial(serial):
    conn = get_products_db()
    cursor = conn.cursor()

    # הוספנו את city_name לשאילתה כדי להתאים למבנה ה-Class
    cursor.execute(
        """
        SELECT id, serial, code, land_type, city_name, status, owner, notes
        FROM products
        WHERE serial = ?
        """,
        (serial,)
    )

    row = cursor.fetchone()
    conn.close()

    if row:
        # המרה של מחרוזת ה-notes מה-DB לרשימה (List[str]) עבור ה-Constructor
        # אם ה-notes ב-DB הם "הערה1,הערה2", זה יהפוך ל-['הערה1', 'הערה2']
        data = list(row)
        raw_notes = data[7]
        data[7] = raw_notes.split(',') if raw_notes else []

        return Product(*data)
    return None

# ------------------ Routes ------------------
@app.route("/", methods=["GET", "POST"])
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

    product = None

    if request.method == "POST":
        serial = request.form.get("serial", "").strip()
        if serial:
            product = get_product_by_serial(serial)

    cities_dir = CITIES_PATH

    cities = []

    for folder in os.listdir(cities_dir):
        folder_path = os.path.join(cities_dir, folder)

        if os.path.isdir(folder_path):
            cities.append({
                "name": folder,
                "title": folder.replace("_", " ").title(),
            })

    remote_list_items = ["עיר חדשה נוספה: חיפה", "תחזוקת שרת ביום ג' בשעה: 11:30", "יש לעדכן חתימות"]
    all_retrun_items = None

    return render_template(
        'index.html',
        user=user if user else None,
        user_code=user.type if user else None,
        global_counts=get_all_status(),
        is_admin=user.is_admin,
        gitLab_logo=gitLab_logo,
        remote_list_items=remote_list_items,
        all_retrun_items=all_retrun_items,
        user_photo=user_photo,
        product=product,
        show_modal=request.method == "POST",
        cities=cities
    )

def getLandType(city_name) ->str:
    file_path = os.path.join(CITIES_PATH, city_name, "General.txt")
    land = get_file_data(file_path, 0)
    return land

def get_all_status():
    conn = get_products_db()
    cursor = conn.cursor()
    # שליפת כל הסטטוסים מכל הערים
    cursor.execute("SELECT status FROM products")
    all_statuses = [row[0] for row in cursor.fetchall()]
    conn.close()

    status_counter = Counter(all_statuses)

    # החזרת מילון מעובד עם שמות הצבעים
    return {
        "RED": status_counter.get("R", 0),
        "WHITE": status_counter.get("W", 0),
        "BLACK": status_counter.get("B", 0),
        "GRAY": status_counter.get("N", 0)  # שימוש ב-'N' עבור סטטוס חדש/אפור
    }

def load_product_by_city(city_name):
    STATUS_MAP = {
        "R": "RED",
        "W": "WHITE",
        "B": "BLACK",
        "N": "NONE"
    }

    products = []
    conn = get_products_db()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT id, serial, code, land_type, city_name, status, owner, notes
        FROM products
        WHERE city_name = ?
        ORDER BY id DESC
    """, (city_name,))

    rows = cursor.fetchall()
    conn.close()

    for row in rows:
        notes_list = row[7].split(",") if row[7] else []

        p = Product(
            id=row[0],
            serial=row[1],
            code=row[2],
            land_type=row[3],
            city_name=row[4],
            status=STATUS_MAP.get(row[5], row[5]),
            owner=row[6],
            notes=notes_list
        )

        products.append(p)

    return products

@app.route("/city/<city_name>/add_product", methods=["POST"])
@login_required
def add_product(city_name):
    serial = request.form.get("serial", "").strip()
    code = request.form.get("code", "").strip()

    if not serial or not code:
        flash("יש למלא מספר סידורי וקוד", "error")
        return redirect(url_for("city_page", city_name=city_name))

    conn = get_products_db()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO products (serial, code, land_type, city_name, status, owner, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (serial, code, getLandType(city_name), city_name, "N", "", ""))
        conn.commit()
        flash("מוצר נוסף בהצלחה", "success")
    except sqlite3.IntegrityError:
        flash("שגיאה: מספר סידורי זה כבר קיים", "error")
    finally:
        conn.close()

    return redirect(url_for("city_page", city_name=city_name))

def get_file_data(path,row_num) -> str:
    with open(path, "r", encoding="utf-8") as f:
        return f.readlines()[row_num].strip()

@app.route("/open-pdf/<path:filepath>")
@login_required
def open_pdf(filepath):
    # Normalize path (prevents ../ tricks)
    filepath = os.path.normpath(filepath)

    # Ensure file exists
    if not os.path.isfile(filepath):
        abort(404)

    # Allow PDFs only
    if not filepath.lower().endswith(".pdf"):
        abort(403)

    return send_file(filepath, as_attachment=False) # open in browser

@app.route("/open_excel/<path:filepath>")
@login_required
def open_excel(filepath):
    # This assumes your paths are stored relative to the project root
    # e.g., "static/cities/London/data.xlsx"
    directory = os.path.dirname(filepath)
    filename = os.path.basename(filepath)

    # Check if file exists to avoid 404 crash
    if not os.path.exists(filepath):
        return "קובץ לא נמצא (File not found)", 404

    return send_from_directory(directory, filename)

@app.route('/get_tests/<serial>')
def get_tests(serial):
    conn = get_tests_db()
    cursor = conn.cursor()

    # שליפת כל העמודות שצריך להציג ב-Frontend
    cursor.execute("""
        SELECT id, test_name, is_passed, test_date, checked_by, is_verified 
        FROM tests 
        WHERE serial = ?
    """, (serial,))

    rows = cursor.fetchall()
    conn.close()

    results = []
    for row in rows:
        results.append({
            "id": row[0],
            "test_name": row[1] or "בדיקת מערכת",  # טיפול במקרה שהשדה ריק
            "is_passed": bool(row[2]),
            # עיצוב התאריך מ-YYYYmmDDHHMMSS לפורמט קריא
            "formatted_date": format_date_helper(row[3]),
            "checked_by": row[4],
            "is_verified": bool(row[5])
        })

    return jsonify(results)

def format_date_helper(date_str):
    if not date_str or len(date_str) < 14: return date_str
    # הופך 20260131195545 ל- 31/01/2026 19:55
    return f"{date_str[6:8]}/{date_str[4:6]}/{date_str[0:4]} {date_str[8:10]}:{date_str[10:12]}"

@app.route('/verify_all_tests/<serial>', methods=['POST'])
def verify_all_tests(serial):
    try:
        conn = get_tests_db()
        cursor = conn.cursor()
        cursor.execute("UPDATE tests SET is_verified = 1 WHERE serial = ?", (serial,))
        conn.commit()
        conn.close()

        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)})

@app.route('/verify_single_test/<int:test_id>', methods=['POST'])
def verify_single_test(test_id):
    try:
        conn = get_tests_db()
        cursor = conn.cursor()
        # Set is_verified to 1 for the specific ID
        cursor.execute("UPDATE tests SET is_verified = 1 WHERE id = ?", (test_id,))
        conn.commit()
        conn.close()
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)})

@app.route('/open_test_file/<int:test_id>')
def open_test_file(test_id):
    conn = get_tests_db()
    cursor = conn.cursor()
    cursor.execute("SELECT excel_str_file FROM tests WHERE id = ?", (test_id,))
    file_name = cursor.fetchone()[0]
    conn.close()

    # שליחת הקובץ מהתיקייה שבה שמורים קבצי הבדיקות
    return send_from_directory('path/to/test_files', file_name)

@app.route("/update_city_info/<city_name>", methods=["POST"])
@login_required
def update_city_info(city_name):
    user = get_current_user()
    if not user or not user.admin_check():
        return "Unauthorized", 403

    # Get paths from form
    p1 = request.form.get("path1", "").strip()
    p2 = request.form.get("path2", "").strip()
    p3 = request.form.get("path3", "").strip()

    # Server-side validation
    if (p1 and not p1.lower().endswith('.pdf')) or (p2 and not p2.lower().endswith('.pdf')):
        # You could use flash() here to show an error message on the UI
        return "Error: File 1 and 2 must be PDF files", 400

    if p3 and not p3.lower().endswith('.xlsx'):
        return "Error: File 3 must be an XLSX file", 400

    file_path = os.path.join(CITIES_PATH, city_name, "General.txt")

    lines = [
        get_file_data(file_path,0),
        request.form.get("des", "").replace("\n", " "),
        request.form.get("file_title1", ""),
        request.form.get("des1", ""),
        p1,
        request.form.get("file_title2", ""),
        request.form.get("des2", ""),
        p2,
        request.form.get("file_title3", ""),
        request.form.get("des3", ""),
        p3
    ]

    with open(file_path, 'w', encoding='utf-8') as f:
        for line in lines:
            f.write(line + "\n")

    return redirect(url_for('city_page', city_name=city_name))

@app.route("/city_page/<city_name>")
@login_required
def city_page(city_name):
    user = get_current_user()
    session['user_type'] = user.type
    if not user:
        return redirect(url_for('login'))

    products = load_product_by_city(city_name)

    # תיקון הספירה: load_product_by_city כבר הפך את p.status למילים (RED, WHITE...)
    status_counter = Counter(p.status for p in products)

    counts = {
        "RED": status_counter.get("RED", 0),
        "WHITE": status_counter.get("WHITE", 0),
        "BLACK": status_counter.get("BLACK", 0)
    }

    # תיקון gray_value: הסטטוס N הפך למילה NONE בתוך load_product_by_city
    gray_value = status_counter.get("NONE", 0)

    # שליפת נתונים לדיאלוג הגלובלי - פותר את ה-UndefinedError
    global_counts = get_all_status()
    sync_city_files_to_db(city_name)
    file_path = os.path.join(CITIES_PATH, city_name, "General.txt")
    total_codes = Codes.get_codes_by_city_list(city_name)

    return render_template(
        "city_page.html",
        user=user,
        is_admin=user.admin_check(),
        gray_value=gray_value,
        city_name=city_name,
        global_counts=global_counts,
        land_type=get_file_data(file_path, 0),
        products=products,
        counts=counts,
        des=get_file_data(file_path, 1),
        # File 1
        file_title1=get_file_data(file_path, 2),
        des1=get_file_data(file_path, 3),
        path1=get_file_data(file_path, 4),  # New specific variable for dialog

        # File 2
        file_title2=get_file_data(file_path, 5),
        des2=get_file_data(file_path, 6),
        path2=get_file_data(file_path, 7),  # New specific variable for dialog

        # File 3
        file_title3=get_file_data(file_path, 8),
        des3=get_file_data(file_path, 9),
        path3=get_file_data(file_path, 10),  # New specific variable for dialog

        # This list can be used for the download links on the page
        pdf_paths=[
            get_file_data(file_path, 4),
            get_file_data(file_path, 7),
            get_file_data(file_path, 10)
        ],
        all_codes=sorted(total_codes)
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

# ------------------ Admin Routes ------------------
def sync_city_files_to_db(city_name):
    city_folder = os.path.join(app.root_path, 'templates', 'cities', city_name)

    if not os.path.exists(city_folder):
        return

    conn = get_tests_db()
    cursor = conn.cursor()

    # יצירת הטבלה (ליתר ביטחון)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS tests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            serial TEXT NOT NULL,
            test_name TEXT,
            city_name TEXT,
            test_level INTEGER NOT NULL,
            checked_by TEXT NOT NULL,
            is_passed INTEGER DEFAULT 0,
            excel_str_file TEXT,
            test_date TEXT,
            is_verified INTEGER DEFAULT 0
        )
    """)

    cursor.execute("SELECT excel_str_file FROM tests")
    existing_files = {row[0] for row in cursor.fetchall()}

    for filename in os.listdir(city_folder):
        if filename.startswith(city_name) and filename.endswith(".txt") and filename not in existing_files:
            try:
                # 1. הסרת שם העיר מההתחלה
                content = filename[len(city_name):]

                # 2. שימוש ב-Regex חכם שמחפש 14 ספרות שמתחילות ב-"202" (עבור שנת 202x)
                # זה מונע ממנו לעצור על ה-00129 של הסריאל
                match = re.search(r'(202\d{11})', content)

                if match:
                    date_string = match.group(1)
                    start_pos, end_pos = match.span()

                    # 3. חילוץ הסריאל המלא: כל מה שלפני התאריך
                    # אם התוכן הוא "sn-001292026...", ה-start_pos יהיה בדיוק אחרי ה-00129
                    raw_serial = content[:start_pos]
                    serial = raw_serial.upper()  # ייתן SN-00129

                    # 4. חילוץ הבודק: כל מה שאחרי התאריך
                    after_date = content[end_pos:].replace(".txt", "")
                    checked_by_clean = re.sub(r'unit\d*', '', after_date).replace('_', ' ').strip()

                    # 5. שם הבדיקה
                    test_name = "BEFORETEST1" if "BEFORETEST1" in filename else "INITTEST"

                    cursor.execute("""
                        INSERT INTO tests (serial, test_name, city_name, test_level, checked_by, is_passed, excel_str_file, test_date, is_verified)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (serial, test_name, city_name, 1, checked_by_clean, 1, filename, date_string, 0))
                else:
                    print(f"DEBUG: Could not find valid 202x date in {filename}")

            except Exception as e:
                print(f"Error processing {filename}: {e}")

    conn.commit()
    conn.close()

@app.route('/update_product_status', methods=['POST'])
def update_product_status():
    user_type = session.get('user_type')
    if user_type not in [0, 1]:
        return jsonify({"success": False, "message": "Unauthorized"}), 403

    data = request.get_json()
    serial = data.get('serial')
    full_status = data.get('status')  # יקבל 'RED', 'BLACK' וכו'

    # מילון תרגום למניעת שגיאת CHECK constraint
    status_map = {
        'RED': 'R',
        'BLACK': 'B',
        'WHITE': 'W',
        'NONE': 'N'
    }

    # המרת הסטטוס לאות אחת, אם לא נמצא במילון - נשמור את המקור
    db_status = status_map.get(full_status, full_status)

    try:
        conn = get_products_db()  # ודא שזו פונקציית החיבור שלך
        cursor = conn.cursor()

        cursor.execute("UPDATE products SET status = ? WHERE serial = ?", (db_status, serial))
        conn.commit()
        conn.close()

        return jsonify({"success": True})
    except Exception as e:
        print(f"Error: {e}")
        return jsonify({"success": False, "message": str(e)})

@app.route('/add_code', methods=['POST'])
def add_code_route():
    data = request.json
    city = data.get('city_name')
    new_code = data.get('code')

    if not city or not new_code:
        return jsonify({"success": False, "message": "נתונים חסרים"}), 400

    # 1. בדיקה גלובלית - האם הקוד קיים בעיר כלשהי במערכת?
    if not Codes.is_code_globally_unique(new_code):
        message = f"הקוד {new_code} כבר תפוס על ידי עיר אחרת!"
        flash(message, "error")
        return jsonify({"success": False, "message": message})

    # 2. ניסיון לשלוף את העיר הנוכחית
    city_obj = Codes.get_codes_by_city(city)

    # 3. אם העיר לא קיימת, ניצור אובייקט חדש
    if not city_obj:
        last_id = Codes.get_last_id()
        city_obj = Codes(id=(last_id or 0) + 1, city_name=city)

    # 4. הוספה ושמירה (הקוד כבר הוכח כייחודי בבדיקה למעלה)
    city_obj.all_codes.append(new_code)
    city_obj.save_to_db()

    flash(f"הקוד {new_code} נוסף בהצלחה לעיר {city}", "success")
    return jsonify({"success": True, "message": "הקוד נוסף בהצלחה"})

@app.route('/remove_code', methods=['POST'])
def remove_code_route():
    data = request.json
    city_name = data.get('city_name')
    code_to_remove = data.get('code')

    city_obj = Codes.get_codes_by_city(city_name)

    if city_obj and code_to_remove in city_obj.all_codes:
        city_obj.all_codes.remove(code_to_remove)
        city_obj.save_to_db()
        return jsonify({"success": True, "message": "הקוד הוסר"})

    return jsonify({"success": False, "message": "הקוד לא נמצא"}), 404

@app.route('/newItems')
@login_required
def newItems():
    user = get_current_user()

    cities_dir = CITIES_PATH
    cities = []
    for folder in os.listdir(cities_dir):
        folder_path = os.path.join(cities_dir, folder)

        if os.path.isdir(folder_path):
            cities.append({
                "name": folder,
                "title": folder.replace("_", " ").title(),
            })

    existing_codes = Codes.get_all_city_codes()

    return render_template("new_items.html", user=user, cities=cities, existing_codes=existing_codes)

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
