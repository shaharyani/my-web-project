import json
import sqlite3
from traceback import print_tb

from flask import Flask, session, redirect, render_template, url_for, make_response, send_file, abort, send_from_directory, request, jsonify, flash
from functools import wraps
from flask_login import LoginManager
import re
from collections import Counter
from werkzeug.security import generate_password_hash
from werkzeug.utils import secure_filename
from static.helper.APIFlusk import api_process_warehouse_transfer, api_update_process_users_transfer, api_receive_warehouse_transfer, api_send_all_product_owners, api_send_all_product_status, api_update_product_status
from Codes import Codes
from Product import Product
from Report import Report
from Request import Request
from User import User
from datetime import datetime
import logging
from logging.handlers import RotatingFileHandler
from static.helper.AppContns import UPLOAD_FOLDER, REPORT_FOLDER, LOG_FILE, CITIES_PATH, DATA_FILE, WAREHOUSE_FILE, LOG_TEST_FILE, LOG_SIGN_FILE, LOG_REPORT_FILE, LOG_REQ_WAREHOUSE_FILE, LOG_SPECIAL_FILE
from static.helper.EmailManager import EmailManager
from static.helper.LogCreator import create_logger
from static.helper.db import get_users_db, get_products_db, get_tests_db, get_reports_db, get_requests_db
import os
from static.helper.dbCreator import create_all_dbs

app = Flask(__name__)
app.secret_key = '27653sdvft&@gbadhsf7231ah!368'
app.jinja_env.filters['from_json'] = json.loads
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login"

app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "gif"}

app.config['REPORT_FOLDER'] = REPORT_FOLDER
os.makedirs(REPORT_FOLDER, exist_ok=True)

create_all_dbs()

test_logger = create_logger('test_logger')
sign_logger = create_logger('sign_logger')
report_logger = create_logger('report_logger')
request_warehouse_logger = create_logger('request_warehouse')
special_logger = create_logger('special')

app.logger.handlers.clear() # Clear default handlers -
app_handler = RotatingFileHandler(LOG_FILE, maxBytes=1_000_000, backupCount=5, encoding="utf-8")
app_handler.setFormatter(logging.Formatter("[%(asctime)s] %(levelname)s: %(message)s"))
app.logger.addHandler(app_handler)
app.logger.setLevel(logging.INFO)

@app.errorhandler(404)
def page_not_found(e):
    return render_template("404.html"), 404

@app.errorhandler(405)
def method_not_supported(e):
    return render_template("405.html"), 404

@app.errorhandler(401)
def page_unauthorized(e):
    return render_template("401.html"), 401

def get_logs(limit=6, file=None):
    logs = []
    if os.path.exists(file):
        with open(file, "r", encoding="utf-8") as f:
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


@app.route('/login/sso')
def sso_login():
    # כאן תבוא הלוגיקה שתלויה בספק ה-SSO שלך
    # דוגמה לניתוב חיצוני (למשל ל-Azure AD או Google):
    # sso_url = "https://login.microsoftonline.com/common/oauth2/v2.0/authorize?..."

    # לצורך הפיתוח שלך, נפנה לנתיב שמטפל באימות:
    return redirect(url_for('auth_process'))


@app.route('/auth/callback')
def auth_callback():
    # כאן השרת החיצוני מחזיר את המשתמש עם "Token"
    # עליך לאמת את ה-Token ולמצוא את המשתמש ב-DB שלך
    user_email = "user@company.com"  # נשלף מה-Token

    # בדיקה אם המשתמש קיים ב-SQLite שלך
    conn = get_users_db()
    conn.row_factory = sqlite3.Row  # מאפשר גישה לפי שם עמודה
    cursor = conn.cursor()

    # בדיקה אם המשתמש קיים בטבלה
    cursor.execute("SELECT * FROM users WHERE email = ?", (user_email,))
    user = cursor.fetchone()

    if user:
        session['user_id'] = user['id']
        return redirect(url_for('admin_dashboard'))
    else:
        return "משתמש לא מורשה במערכת", 403

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
        SELECT id, serial, code, land_type, city_name, status, owner, notes, report_count, count
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

    all_products = get_all_products_from_db()
    all_retrun_items = [p for p in all_products if p.owner == 'מחסן']
    all_cities = sorted(list(set(p.city_name for p in all_products if p.city_name)))

    return render_template(
        'index.html',
        user=user if user else None,
        user_code=user.type if user else None,
        global_counts=get_all_status(),
        is_admin=user.is_admin,
        gitLab_logo=gitLab_logo,
        remote_list_items=get_announcements(DATA_FILE),
        all_retrun_items=all_retrun_items,
        user_photo=user_photo,
        product=product,
        show_modal=request.method == "POST",
        cities=cities,
        all_cities=all_cities,
        all_products=all_products
    )

def getLandType(city_name) -> str:
    file_path = os.path.join(CITIES_PATH, city_name, "General.txt")
    land = get_file_data(file_path, 0)
    return land

def get_announcements(file=DATA_FILE):
    """Reads the txt file and returns a list of strings."""
    if not os.path.exists(file):
        return []
    with open(file, "r", encoding="utf-8") as f:
        # .read().splitlines() handles newlines cleanly
        return f.read().splitlines()

@app.route('/admin/update_announcements', methods=['POST'])
def update_announcements():
    # Get the text from the textarea
    raw_text = request.form.get('updates_text', '')
    file = DATA_FILE if request.form.get("target_file") == "announcements" else WAREHOUSE_FILE

    # 1. Split into lines, strip spaces, and remove empty entries
    all_lines = [line.strip() for line in raw_text.split('\n') if line.strip()]
    # 2. Slice the list to keep ONLY the first 4 items
    announcements_list = all_lines[:4]
    # 3. Save to the txt file
    with open(file, "w", encoding="utf-8") as f:
        f.write("\n".join(announcements_list))

    if file == DATA_FILE:
        flash("עדכונים נשמרו בהצלחה", "success")
    else:
        flash("הנחיות עודכנו בהצלחה", "success")
    return redirect(url_for('admin_dashboard'))

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
        SELECT id, serial, code, land_type, city_name, status, owner, notes, report_count, count
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
            notes=notes_list,
            reports_count=row[8],
            count=row[9]
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
            INSERT INTO products (serial, code, land_type, city_name, status, owner, notes, report)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (serial, code, getLandType(city_name), city_name, "N", "מחסן", ""), 0)
        conn.commit()
        flash("מוצר נוסף בהצלחה", "success")
    except sqlite3.IntegrityError as e:
        # Check the error message to see which constraint failed
        error_msg = str(e).lower()
        if "serial" in error_msg:
            flash("שגיאה: המספר הסידורי כבר קיים במערכת", "error")
        elif "code" in error_msg:
            flash("שגיאה: הקוד כבר קיים במערכת", "error")
        else:
            flash("שגיאה: הנתונים כבר קיימים במערכת", "error")
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

def format_date_helper(date_str) -> str:
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
        p3,
        get_file_data(file_path, 11)
    ]

    with open(file_path, 'w', encoding='utf-8') as f:
        for line in lines:
            f.write(line + "\n")

    return redirect(url_for('city_page', city_name=city_name))

@app.route("/set_eme_amount/<city_name>", methods=["POST"])
@login_required
def set_eme_amount(city_name):
    user = get_current_user()
    if not user or not user.admin_check():
        return "Unauthorized", 403

    amount_eme = request.form.get("amount_eme", "").strip()
    if not amount_eme:
        flash("ערך חירום לא הוגדר", "error")
    elif int(amount_eme) <= 0:
        flash("כמות לחירום מחוייבת", "error")
    else:
        flash("כמות חירום הוגדרה בהצלחה", "success")
        file_path = os.path.join(CITIES_PATH, city_name, "General.txt")
        line_to_change = 11
        new_data = amount_eme + "\n"

        with open(file_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        lines.insert(line_to_change, new_data)

        with open(file_path, 'w', encoding='utf-8') as f:
            f.writelines(lines)

    return redirect(url_for('city_page', city_name=city_name, amount_eme=amount_eme))


@app.route("/get_notes/<serial>")
@login_required
def get_notes(serial):
    conn = get_products_db()
    product = conn.execute('SELECT notes FROM products WHERE serial = ?', (serial,)).fetchone()
    conn.close()

    if product:
        raw_notes = product[0] if product[0] else "[]"
        notes_data = json.loads(raw_notes)
        return jsonify({'notes': notes_data})  # כאן Flask הופך את זה ל-JSON תקין ל-JS

    return jsonify({'notes': []})

@app.route("/add_note", methods=["POST"])
@login_required
def add_note():
    data = request.get_json()
    serial = data.get('serial')
    note_text = data.get('text')

    if not serial or not note_text:
        return jsonify({'status': 'error', 'message': 'Missing data'}), 400

    conn = get_products_db()
    try:
        product = conn.execute('SELECT notes FROM products WHERE serial = ?', (serial,)).fetchone()

        if product is None:
            return jsonify({'status': 'error', 'message': 'Product not found'}), 404

        try:
            current_notes = json.loads(product['notes']) if product['notes'] else []
        except (ValueError, TypeError):
            current_notes = []

        new_note = {
            'date': datetime.now().strftime("%d/%m/%Y %H:%M"),
            'text': note_text,
            'user': get_current_user().name  # מוסיף גם מי כתב את ההערה לתיעוד
        }

        current_notes.append(new_note)

        conn.execute('UPDATE products SET notes = ? WHERE serial = ?',
                     (json.dumps(current_notes, ensure_ascii=False), serial))
        conn.commit()

        return jsonify({'status': 'success', 'notes_count': len(current_notes)})

    except Exception as e:
        print(f"Error adding note: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500
    finally:
        conn.close()

@app.route("/delete_note", methods=["POST"])
@login_required
def delete_note():
    data = request.get_json()
    serial = data.get('serial')
    note_index = data.get('index')  # האינדקס של ההערה ברשימה

    conn = get_products_db()
    product = conn.execute('SELECT notes FROM products WHERE serial = ?', (serial,)).fetchone()

    if product and product[0]:
        notes_list = json.loads(product[0])

        if 0 <= note_index < len(notes_list):
            del notes_list[note_index]

            conn.execute('UPDATE products SET notes = ? WHERE serial = ?',
                         (json.dumps(notes_list, ensure_ascii=False), serial))
            conn.commit()
            conn.close()
            return jsonify({'status': 'success', 'remaining': len(notes_list)})

    conn.close()
    return jsonify({'status': 'error', 'message': 'Could not delete note'}), 400

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
        "BLACK": status_counter.get("BLACK", 0),
        "GRAY": status_counter.get("NONE", 0)
    }

    # תיקון gray_value: הסטטוס N הפך למילה NONE בתוך load_product_by_city
    gray_value = status_counter.get("NONE", 0)

    # שליפת נתונים לדיאלוג הגלובלי - פותר את ה-UndefinedError
    global_counts = get_all_status()
    sync_city_files_to_db(city_name)
    file_path = os.path.join(CITIES_PATH, city_name, "General.txt")
    total_codes = Codes.get_codes_by_city_list(city_name)
    all_return_items = [p for p in get_all_products_from_db() if str(p.owner).strip() == 'מחסן' and p.status.upper() in ['WHITE', 'BLACK'] and p.city_name == city_name]
    all_return_white = [p for p in all_return_items if p.status.upper() == 'WHITE' and p.city_name == city_name]
    amount_current_serials = len(all_return_items)
    amount_current_white_serials = len(all_return_white)

    return render_template(
        "city_page.html",
        user=user,
        is_admin=user.admin_check(),
        editor=user.type == 1,
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
        all_codes=sorted(total_codes),
        amount_eme=get_file_data(file_path, 11),
        amount_current_serials=amount_current_serials,
        amount_current_white_serials=amount_current_white_serials
    )

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        user_name = request.form.get("name", "").strip()
        user_password = request.form.get("password")
        remember = request.form.get("remember")

        if not user_name or not user_password:
            flash("נא להזין שם משתמש וסיסמה", "warning")
            return render_template("login.html")

        # Use a robust DB lookup
        temp_user = User.get_by_name(user_name)

        if temp_user and temp_user.check_password(user_password):
            # 1. Clear any old session data to prevent session fixation
            session.clear()

            # 2. Store unique identity in the session
            session["user_id"] = temp_user.id  # Better than just name
            session["user_name"] = temp_user.name

            # 3. DB Update for this specific user only
            temp_user.activate()

            flash(f"שלום {temp_user.name}", "success")
            app.logger.info(f"User '{temp_user.name}' logged in.")

            response = make_response(redirect("/"))

            # 4. Handle "Remember Me" securely
            if remember == "on":
                # Max age: 30 days
                response.set_cookie("remember_user", temp_user.name,
                                    max_age=60 * 60 * 24 * 30, httponly=True)
            else:
                response.delete_cookie("remember_user")

            return response

        else:
            flash("שם משתמש או סיסמה שגויים", "error")
            app.logger.warning(f"Login failed for '{user_name}'.")
            return render_template("login.html")

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
    flash("ההתנתקות בוצעה בהצלחה", "success")
    app.logger.info(f"User '{user.name}' logged out successfully." if user else "Unknown user logged out.")
    return response

# ------------------ Admin Routes ------------------
def sync_city_files_to_db(city_name):
    # Base path for the city folders
    city_folder = os.path.join(CITIES_PATH, city_name)

    # Subfolders mapped to test levels
    subfolders = {
        "InitTest": 1,
        "AfterR2": 2,
        "AfterHARAZA": 3
    }

    if not os.path.exists(city_folder):
        return

    conn = get_tests_db()
    cursor = conn.cursor()

    for folder_name, level in subfolders.items():
        folder_path = os.path.join(city_folder, folder_name)
        if not os.path.exists(folder_path):
            continue

        for filename in os.listdir(folder_path):
            if filename.endswith(".txt"):
                # Use filename without extension as test_name
                test_name = os.path.splitext(filename)[0]

                # Check if this specific file is already in the DB
                cursor.execute("SELECT id FROM tests WHERE excel_str_file = ?", (filename,))
                if cursor.fetchone():
                    continue

                try:
                    # Parsing Serial and Date from filename (based on your existing logic)
                    content = filename[len(city_name):]
                    match = re.search(r'(202\d{11})', content)

                    if match:
                        date_string = match.group(1)
                        start_pos, end_pos = match.span()
                        serial = content[:start_pos].upper()

                        after_date = content[end_pos:].replace(".txt", "")
                        checked_by = re.sub(r'unit\d*', '', after_date).replace('_', ' ').strip()

                        cursor.execute("""
                                INSERT INTO tests (serial, test_name, city_name, test_level, checked_by, is_passed, excel_str_file, test_date, is_verified)
                                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                            """, (serial, folder_name, city_name, level, checked_by, 0, filename, date_string, 0))
                except Exception as e:
                    app.logger.error(f"Error syncing {filename}: {e}")

    conn.commit()
    conn.close()

@app.route('/update_tests_status_bulk', methods=['POST'])
def update_tests_status_bulk():
    data = request.get_json()
    passed_ids = data.get('passed_ids', [])
    failed_ids = data.get('failed_ids', [])
    serial = data.get('serial', 'Unknown')
    user_name = session.get('user_name', 'System')

    try:
        conn = get_tests_db()  # Use your specific DB connection function
        cursor = conn.cursor()

        # 1. Update tests to PASSED
        if passed_ids:
            placeholders = ', '.join(['?'] * len(passed_ids))
            cursor.execute(f"UPDATE tests SET is_passed = 1 WHERE id IN ({placeholders})", passed_ids)
            test_logger.info(f"User '{user_name}' set tests {passed_ids} to PASSED for product {serial}")

            # Force flush to ensure it writes to disk immediately
            for handler in test_logger.handlers:
                handler.flush()

        # 2. Update tests to FAILED
        if failed_ids:
            placeholders = ', '.join(['?'] * len(failed_ids))
            cursor.execute(f"UPDATE tests SET is_passed = 0 WHERE id IN ({placeholders})", failed_ids)
            test_logger.info(f"User '{user_name}' set tests {failed_ids} to FAILED for product {serial}")

            # Force flush to ensure it writes to disk immediately
            for handler in test_logger.handlers:
                handler.flush()

        conn.commit()
        conn.close()
        return jsonify(success=True)
    except Exception as e:
        if 'conn' in locals(): conn.close()
        test_logger.error(f"Failed status update for {serial}: {str(e)}")
        return jsonify(success=False, message=str(e))

@app.route('/update_verification_bulk', methods=['POST'])
@login_required
def update_verification_bulk():
    data = request.get_json()
    serial = data.get('serial', 'Unknown')
    user_name = session.get('user_name', 'System')

    # These must match the names used in your JS body: JSON.stringify({...})
    verified_ids = data.get('verified_ids', [])
    unverified_ids = data.get('unverified_ids', [])

    conn = get_tests_db()
    cursor = conn.cursor()

    try:
        # 1. Update tests that should be verified (🛡️)
        if verified_ids:
            placeholders = ', '.join(['?'] * len(verified_ids))
            cursor.execute(f"UPDATE tests SET is_verified = 1 WHERE id IN ({placeholders})", verified_ids)
            test_logger.info(f"User '{user_name}' VERIFIED tests {verified_ids} for product {serial}")

            # Force flush to ensure it writes to disk immediately
            for handler in test_logger.handlers:
                handler.flush()

        # 2. Update tests that were unchecked (⏳)
        if unverified_ids:
            placeholders = ', '.join(['?'] * len(unverified_ids))
            cursor.execute(f"UPDATE tests SET is_verified = 0 WHERE id IN ({placeholders})", unverified_ids)
            test_logger.info(f"User '{user_name}' UN-VERIFIED tests {unverified_ids} for product {serial}")

            # Force flush to ensure it writes to disk immediately
            for handler in app.logger.handlers:
                handler.flush()

        conn.commit()
        return jsonify(success=True)

    except Exception as e:
        conn.rollback()
        test_logger.error(f"Error updating verification for {serial}: {str(e)}")
        return jsonify(success=False, message=str(e))

    finally:
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
        api_update_product_status(serial, db_status)
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
        message = f"הקוד {new_code} כבר תפוס על ידי עיר אחרת"
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

@app.route('/create_user', methods=['POST'])
@login_required
def create_user():
    # 1. Identity Check
    current_user = User.get_by_name(session.get("user_name"))
    if not current_user or not current_user.is_admin:
        flash("אינך מורשה לבצע פעולה זו.", "error")
        return redirect(url_for('admin_dashboard'))

    # 2. Data Extraction
    name = request.form.get('name', '').strip()
    mador = request.form.get('mador', '').strip()
    raw_password = request.form.get('password')
    user_type = int(request.form.get('type', 2))
    is_active = request.form.get('is_active') == 'on'
    is_admin = (user_type == 0)
    email = request.form.get('email')

    # 3. Validation
    if not name or not raw_password:
        flash("חובה להזין שם משתמש וסיסמה.", "error")
        return redirect(url_for('admin_dashboard'))

    if not email:
        flash("חובה מייל.", "error")
        return redirect(url_for('admin_dashboard'))

    if User.get_by_name(name):
        flash(f"המשתמש '{name}' כבר קיים במערכת.", "error")
        return redirect(url_for('admin_dashboard'))

    try:
        last_login = datetime.now().strftime("%H:%M %d/%m/%Y")

        new_user = User.create(
            name=name,
            mador=mador,
            password=raw_password,
            type=user_type,
            is_active=is_active,
            is_admin=is_admin,
            last_login=last_login,
            email=email
        )

        subject = f" נוצר בהצלחה{new_user.name}המשתמש "
        body = ""
        email_sender(current_user, new_user.email, subject, body)

        flash(f"המשתמש {name} נוצר בהצלחה.", "success")
    except Exception as e:
        app.logger.error(f"Error creating user: {e}")
        flash("שגיאה ביצירת המשתמש. נסה שוב מאוחר יותר.", "error")

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
    email = request.form.get("email")
    is_admin = "is_admin" in request.form
    user_type = request.form.get("type")

    try:
        user_type = int(user_type)
    except (ValueError, TypeError):
        user_type = 0  # default type if missing

    user = User.get_by_name(name)
    if not user:
        flash("לא ניתן לערוך את המשתמש", "error")
        return redirect(url_for("admin_dashboard"))

    # Update fields
    user.mador = mador
    user.type = 2 if is_admin else user_type
    user.is_admin = True if user.type == 0 else False
    user.email = email

    # Update DB fields
    user.update_db_field("mador", user.mador)
    user.update_db_field("type", user.type)
    user.update_db_field("is_admin", int(user.is_admin))
    user.update_db_field("email", user.email)

    flash("המשתמש עודכן בהצלחה", "success")
    app.logger.info(
        f"User '{user.name}' (ID: {user.id}) updated: type={user.type}, admin={user.is_admin} by {current_user.name}."
    )

    subject = f"{user.name}עדכן פרטי המשתמש "
    body = ""
    email_sender(current_user, user.email, subject, body)

    return redirect(url_for("admin_dashboard"))

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

    subject = "עדכן סיסמא"
    body = ""
    email_sender(get_current_user(), user.email, subject, body)

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

        subject = "מחיקת חשבון במצב הגלים"
        body = ""
        email_sender(current_user, user_to_delete.email, subject, body)
    else:
        flash(f"User {username} not found.", "error")

    return redirect(url_for('admin_dashboard'))

@app.route('/get_admin_emails', methods=['GET'])
@login_required
def get_admin_emails():
    try:
        conn = get_users_db()
        cursor = conn.cursor()

        cursor.execute("SELECT email FROM users WHERE type = 0 AND email IS NOT NULL")
        emails = [row[0] for row in cursor.fetchall()]

        conn.close()
        return jsonify({'success': True, 'emails': emails})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route("/admin")
@login_required
def admin_dashboard():
    current_user = get_current_user()
    if not current_user or not current_user.is_admin:
        flash("למשתמש זה אין הרשאות מנהל", "error")
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
            name=row[1], mador=row[2], id=row[0], password=row[3],
            type=row[4], is_active=bool(row[5]), is_admin=bool(row[6]),
            last_login=row[7], profile_image=row[8] if row[8] else "user_photo.png", email=row[9],
        )
        users.append(u)

    return render_template(
        "admin.html",
        user=current_user.get_name(),
        users=users,
        today=str(datetime.now()),
        all_warehouse_requests= [req for req in get_all_product_requests_from_db() if req["to_user"] == "מחסן"],
        all_special = get_all_special_requests(),
        logs=get_logs(9,LOG_FILE),
        test_logs=get_logs(5,LOG_TEST_FILE),
        sign_logs=get_logs(10,LOG_SIGN_FILE),
        report_logs=get_logs(6,LOG_REPORT_FILE),
        request_warehouse_logger=get_logs(9,LOG_REQ_WAREHOUSE_FILE),
        special_logger=get_logs(9,LOG_SPECIAL_FILE),
        announcements=get_announcements(DATA_FILE),
        des_content=get_announcements(WAREHOUSE_FILE)
    )

@app.route('/update_request_date/<int:req_id>', methods=['POST'])
@login_required
def update_request_date(req_id):
    data = request.get_json()
    new_date = data.get('finish_date')

    if not new_date:
        return jsonify({'success': False, 'error': 'תאריך חסר'})

    try:
        conn = get_requests_db()
        conn.execute('UPDATE requests SET finish_date = ? WHERE id = ?', (new_date, req_id))
        conn.commit()
        conn.close()
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

def email_sender(user, recipient, subject, body):
    server_info = {
        'host': 'smtp.office365.com',
        'port': 587,
        'user': user.email,
        'password': user.password,
        'MAIL_USE_TLS': True,
        'MAIL_USE_SSL': False,
    }

    manager = EmailManager()
    manager.send_async(
        server_config=server_info,
        recipient_email=recipient,
        subject=subject,
        body_html=body
    )

@app.route('/send_quick_email', methods=['POST'])
@login_required
def send_quick_email():
    data = request.get_json()
    user = get_current_user()

    server_info = {
        'host': 'smtp.office365.com',
        'port': 587,
        'user': user.email,
        'password': user.password,
    }

    manager = EmailManager()
    manager.send_async(
        server_config=server_info,
        recipient_email=data.get('recipient'),
        subject=data.get('subject'),
        body_html=data.get('body')
    )

    return jsonify({'success': True})

@app.route('/reset_password_to_default', methods=['POST'])
@login_required
def reset_password_to_default():
    data = request.get_json()
    user_id = data.get('user_id')

    try:
        conn = get_users_db()
        cursor = conn.cursor()

        hashed_password = generate_password_hash('123')
        cursor.execute("UPDATE users SET password = ? WHERE id = ?", (hashed_password, user_id))
        conn.commit()

        cursor.execute("SELECT email FROM users WHERE id = ?", user_id)
        email_to_send = cursor.fetchall()[0][0]

        subject = "הסיסמא עודכנה ל-123"
        body = ""
        email_sender(get_current_user(), email_to_send, subject, body)

        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route("/get_serial_history/<serial>")
def get_serial_history(serial):
    sign_logs = get_logs(0, LOG_SIGN_FILE)

    if not sign_logs:
        return jsonify({'success': False, 'message': 'אין נתונים זמינים'})

    serial_logs = [log for log in sign_logs if serial in log['message']]

    history_data = [
        {'timestamp': log['timestamp'], 'level': log['level'], 'message': log['message']}
        for log in serial_logs
    ]

    if history_data:
        return jsonify({'success': True, 'history': history_data})
    else:
        return jsonify({'success': False, 'message': 'לא נמצאה היסטוריה עבור סיראלי זה'})

@app.route('/handle_request/<request_id>/<action>', methods=['POST'])
def handle_request(request_id, action):
    conn = get_requests_db()  # חיבור לטבלאות הבקשות
    conn1 = get_products_db()  # חיבור לטבלת המוצרים
    admin_user = get_current_user()

    try:
        cursor = conn.cursor()
        cursor1 = conn1.cursor()

        cursor.execute("SELECT serial, user FROM product_requests WHERE id = ?", (request_id,))
        req = cursor.fetchone()

        if not req:
            return jsonify({'success': False, 'error': 'הבקשה לא נמצאה'})

        serial, user_name = req

        if action == 'approve':
            cursor1.execute("UPDATE products SET owner = ? WHERE serial = ?", (user_name, serial))
            conn1.commit()

            request_warehouse_logger.info(f"ADMIN '{admin_user.name}' APPROVED to '{user_name}' the {serial} from warehouse")
            sign_logger.info(f"User '{user_name}' signed for the {serial} from warehouse")

            cursor1.execute("""
                                UPDATE products 
                                SET count = count + 1 
                                WHERE serial = ?
                            """, (serial,))
            conn1.commit()

            cursor.execute("UPDATE product_requests SET status = ? WHERE id = ?", ('אושר', request_id))
            conn.commit()
            api_receive_warehouse_transfer(serial, user_name)
            return jsonify({'success': True, 'message': 'הבקשה אושרה'})
        elif action == 'reject':
            cursor.execute("UPDATE product_requests SET status = ? WHERE id = ?", ('סורב', request_id))

            request_warehouse_logger.info(f"ADMIN '{admin_user.name}' REJECTED to '{user_name}' the {serial} from warehouse")
            conn.commit()
            return jsonify({'success': True, 'message': 'הבקשה סורבה'})

        return jsonify({'success': False, 'error': 'פעולה לא חוקית'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})
    finally:
        conn.close()
        conn1.close()

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


@app.route('/check_availability', methods=['POST'])
@login_required
def check_availability():
    data = request.get_json()
    city = data.get('city_name', '').strip()
    code = data.get('code', '').strip()

    existing_codes = Codes.get_all_city_codes()
    existing_cities = Codes.get_all_city_names()
    flat_codes = [item for sublist in existing_codes.values() for item in sublist]

    return jsonify({
        'city_exists': True if city in existing_cities else False,
        'code_exists': True if code in flat_codes else False,
        'existing_city': Codes.get_city_by_code(code) if code != '' else None,
    })

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

def get_all_products_from_db():
    """Fetches all products from the database and returns them as a list of Product objects."""
    products = []
    conn = get_products_db()
    cursor = conn.cursor()

    # Selecting the columns required by the Product class constructor
    cursor.execute("""
        SELECT id, serial, code, land_type, city_name, status, owner, notes, report_count, count 
        FROM products
    """)

    rows = cursor.fetchall()
    conn.close()

    # Mapping status codes to full names for the UI consistency
    STATUS_MAP = {
        "R": "RED",
        "W": "WHITE",
        "B": "BLACK",
        "N": "NONE"
    }
    city_names = []

    for row in rows:
        # Notes are stored as a comma-separated string in DB, convert back to list
        notes_list = row[7].split(",") if row[7] else []
        city_names.append(row[4])
        p = Product(
            id=row[0],
            serial=row[1],
            code=row[2],
            land_type=row[3],
            city_name=row[4],
            status=STATUS_MAP.get(row[5], row[5]),
            owner=row[6],
            notes=notes_list,
            reports_count=row[8],
            count=row[9]
        )
        products.append(p)

    for city_name in city_names:
        api_send_all_product_owners(city_name)
        api_send_all_product_status(city_name)

    return products

def get_all_product_requests_from_db():
    conn = get_requests_db()
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    try:
        cursor.execute("SELECT * FROM product_requests ORDER BY id DESC")
        rows = cursor.fetchall()
        return [dict(row) for row in rows]
    except Exception as e:
        print(f"Error fetching requests: {e}")
        return []
    finally:
        conn.close()

def get_all_special_requests():
    conn = get_requests_db()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id, title, target, description, ask_by, serials, finish_date, request_date, status, total, current FROM requests")
    rows_requests = cursor.fetchall()

    requests_list = []
    for row in rows_requests:
        req = Request(
            id=row[0],
            title=row[1],
            target=row[2],
            description=row[3],
            ask_by=row[4],
            serials=row[5],
            finish_date=row[6],
            request_date=row[7],
            status=row[8],
            total=row[9],
            current=row[10]
        )
        requests_list.append(req)
    conn.close()
    return requests_list

@app.route('/get_special_details/<int:report_id>')
def get_special_details(report_id):
    conn = get_requests_db()
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM requests WHERE id = ?", (report_id,))
    special_request = cursor.fetchone()

    if not special_request:
        conn.close()
        return jsonify({'success': False, 'message': 'הדו"ח לא נמצא'}), 404

    if special_request['serials']:
        auto_refresh_green_status(report_id)

    report_data = {
        'title': special_request['title'],
        'ask_by': special_request['ask_by'],
        'target': special_request['target'],
        'finish_date': special_request['finish_date'],
        'request_date': special_request['request_date'],
        'serials': special_request['serials'],
        'description': special_request['description'],
        'status': special_request['status'],
        'total': special_request['total'],
        'current': special_request['current']
    }
    conn.close()
    return jsonify({
        'success': True,
        'report': report_data
    })

@app.route('/create_special', methods=['POST'])
@login_required
def create_special():
    data = request.get_json()

    title = data.get('title', '').strip()
    target = data.get('target', '').strip()
    description = data.get('description', '').strip()
    finish_date_str = data.get('finish_date')
    serials = ""
    status = "ממתין"
    current = 0
    user = get_current_user()


    if not title or not target or not description or not finish_date_str:
        return jsonify({'success': False, 'message': 'חובה למלא את כל השדות!'}), 400

    try:
        finish_date = datetime.strptime(finish_date_str, '%Y-%m-%d').date()
        if finish_date < datetime.now().date():
            return jsonify({'success': False, 'message': 'לא ניתן לבחור תאריך מהעבר'}), 400
    except ValueError:
        return jsonify({'success': False, 'message': 'פורמט תאריך לא תקין'}), 400

    try:
        conn = get_requests_db()
        cursor = conn.cursor()

        # get the request data (separated by ':')
        parsed_data = []
        for line in description.strip().split('\n'):
            city, action, amount = line.split(':')
            parsed_data.append({
                'city': city,
                'action': action,
                'amount': int(amount),
            })
        total = sum(item['amount'] for item in parsed_data)

        cursor.execute("""
                INSERT INTO requests (title, target, description, serials, finish_date, request_date, ask_by, status, total, current)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (title, target, description, serials, finish_date_str, datetime.now().strftime('%Y-%m-%d'),
                  get_current_user().name, status, total, current))
        special_logger.info(f"USER '{user.name}' CREATED a special request '{title}'")

        subject = f"{title} יצר את הבקשה לצוות {user.name}המשתמש "
        body = ""
        email_sender(get_current_user(), user.email, subject, body)

        conn.commit()
        conn.close()
    except Exception as e:
        return jsonify({'success': False, 'message': f'שגיאת שרת: {str(e)}'}), 500

    return jsonify({'success': True, 'message': 'הבקשה נשלחה בהצלחה'})

@app.route('/delete_special/<int:report_id>', methods=['POST'])
def delete_special(report_id):
    conn = get_requests_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM requests WHERE id = ?", (report_id,))
    special_request = cursor.fetchone()
    title = special_request['title']

    cursor = conn.cursor()
    user = get_current_user()

    cursor.execute("DELETE FROM requests WHERE id = ?", (report_id,))
    conn.commit()

    if cursor.rowcount > 0:
        conn.close()
        if user.is_admin:
            special_logger.info(f"Admin '{user.name}' DELETED '{title}'")

            subject = f"{title} מחק את הבקשה לצוות {user.name}המנהל "
            body = ""
            email_sender(user, user.email, subject, body)
        else:
            special_logger.info(f"USER '{user.name}' DELETED '{title}'")

            subject = f"{title} מחק את הבקשה לצוות {user.name}המשתמש "
            body = ""
            email_sender(user, user.email, subject, body)
        return jsonify({'success': True})
    else:
        conn.close()
        return jsonify({'success': False, 'message': 'הבקשה לא נמצאה'}), 404

@app.route('/handle_special/<int:request_id>', methods=['POST'])
@login_required
def handle_special(request_id):
    data = request.get_json()
    action = data.get('action')  # 'approve' או 'reject'

    # הגדרת הסטטוס הסופי
    new_status = 'בתהליך' if action == 'approve' else 'סורב'
    conn = get_requests_db()
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM requests WHERE id = ?", (request_id,))
    special_request = cursor.fetchone()
    special_serials = special_request['serials']

    if not special_request:
        return jsonify({'success': False, 'message': 'הדו"ח לא נמצא'}), 404
    else:
        if special_serials and special_serials != "[]":
            try:
                cursor.execute("""
                    UPDATE requests 
                    SET status = ? 
                    WHERE id = ?
                """, (new_status, request_id))
                conn.commit()
            except Exception as e:
                conn.close()
                return jsonify({'success': False, 'message': str(e)}), 500
            conn.close()
        elif special_serials == "[]":
            cursor.execute("""
                            UPDATE requests 
                            SET status = ? 
                            WHERE id = ?
                            """, ("סורב", request_id))
            conn.commit()
            conn.close()
        else:
            if new_status == 'approve':
                cursor.execute("""
                                        UPDATE requests 
                                        SET status = ? 
                                        WHERE id = ?
                                    """, ("ממתין", request_id))
                conn.commit()
                conn.close()
            else:
                cursor.execute("""
                                        UPDATE requests 
                                        SET status = ? 
                                        WHERE id = ?
                                    """, ("סורב", request_id))
                conn.commit()
                conn.close()
    return jsonify({
        'success': True,
        'message': f'הבקשה עודכנה לסטטוס: {new_status}'
    })

@app.route('/update_serials', methods=['POST'])
@login_required
def update_serials():
    data = request.get_json()
    request_id = data.get('request_id')
    serials_data = data.get('serials', [])  # רשימה של אובייקטים {line_id, serial, action}
    admin_user = get_current_user()

    if not request_id:
        return jsonify({'success': False, 'message': 'Missing request_id'}), 400

    if not serials_data:
        return jsonify({'success': False, 'message': 'אין כלל סיראליים'}), 404
    else:
        try:
            conn = get_requests_db()
            conn.row_factory = sqlite3.Row  # חובה כדי לגשת לעמודות בשם
            cursor = conn.cursor()

            cursor.execute("SELECT * FROM requests WHERE id = ?", (request_id,))
            request_row = cursor.fetchone()

            if not request_row:
                conn.close()
                return jsonify({'success': False, 'message': 'Request not found'}), 404

            # בניית מפת פעולות מתוך התיאור (בדיוק כמו ברענון)
            description_text = request_row['description'] or ""
            actions_map = {}
            lines = description_text.strip().split('\n')
            for idx, line in enumerate(lines):
                parts = line.split(':')
                if len(parts) >= 2:
                    actions_map[idx] = parts[1].strip()

            processed_serials = []
            current_count = 0

            for item in serials_data:
                l_id = int(item.get('line_id', 0))
                action = actions_map.get(l_id, '')

                # קביעת הסטטוס לבדיקה
                status_to_check = "WHITE" if action == 'הלבנה' else ("BLACK" if action == 'השחרה' else None)

                # בדיקת הסריאלי
                is_green = check_special(item.get('serial'), status_to_check)
                if is_green:
                    current_count += 1

                processed_serials.append({
                    "line_id": l_id,
                    "serial": item.get('serial'),
                    "is_green": is_green,
                    "action": action  # הוספנו את ה-action למבנה כדי שיתאים לרענון
                })

            cursor.execute("""
                    UPDATE requests 
                    SET serials = ?, current = ?, status = 'בתהליך' 
                    WHERE id = ?
                """, (json.dumps(processed_serials), current_count, request_id))

            special_logger.info(f"ADMIN '{admin_user.name}' UPDATED serials for request '{request_id}'")
            #subject = f"{title} עדכן סיראליים לבקשה לצוות {admin_user.name}המנהל "
            #body = ""
            #email_sender(admin_user, user.email, subject, body)

            conn.commit()
            conn.close()
            return jsonify({'success': True, 'message': 'הסריאלים עודכנו בהצלחה', 'current': current_count})
        except Exception as e:
            if 'conn' in locals(): conn.close()
            return jsonify({'success': False, 'message': str(e)}), 500

def check_special(special_serial, status):
    target_status = status.upper().strip()
    target_serial = str(special_serial).strip()

    all_products = get_all_products_from_db()

    for p in all_products:
        p_status = str(p.status).upper().strip()
        p_serial = str(p.serial).strip()
        if p_status == target_status and p_serial == target_serial:
            return True
    return False

@app.route('/trigger_async_refresh/<int:request_id>')
@login_required
def trigger_async_refresh(request_id):
    try:
        auto_refresh_green_status(request_id)

        conn = get_requests_db()
        cursor = conn.cursor()
        cursor.execute("SELECT current, total FROM requests WHERE id = ?", (request_id,))
        row = cursor.fetchone()
        conn.close()

        if row:
            return jsonify({'success': True, 'current': row[0], 'total': row[1]})
        return jsonify({'success': False, 'error': 'Request not found'})

    except Exception as e:
        print(f"Refresh error: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

def auto_refresh_green_status(request_id):
    conn = get_requests_db()
    cursor = conn.cursor()

    cursor.execute("SELECT serials, description, total, current, status FROM requests WHERE id = ?", (request_id,))
    row = cursor.fetchone()

    # הגנה 1: אם השורה לא נמצאה בכלל
    if not row:
        conn.close()
        return

    # הגנה 2: טיפול במקרה שהשדה serials ריק או None
    serials_raw = row[0]
    if not serials_raw:
        print(f"Warning: Serials field is empty for request {request_id}")
        conn.close()
        return

    try:
        serials = json.loads(serials_raw)
    except json.JSONDecodeError:
        print(f"Error: Serials for request {request_id} is not a valid JSON: {serials_raw}")
        conn.close()
        return

    description_text = row[1] or ""
    total = row[2] or 0
    past_current = row[3] or 0

    actions_map = {}
    lines = description_text.strip().split('\n')
    for idx, line in enumerate(lines):
        if ':' in line:
            parts = line.split(':')
            if len(parts) >= 2:
                actions_map[idx] = parts[1].strip()

    current_count = 0

    # הגנה 3: וודא ש-serials הוא אכן רשימה לפני הלולאה
    if isinstance(serials, list):
        for item in serials:
            l_id = int(item.get('line_id', 0))
            action = actions_map.get(l_id, '')

            # ברירת מחדל אם אין פעולה מזוהה
            status_to_check = "WHITE"
            if action == 'הלבנה':
                status_to_check = "WHITE"
            elif action == 'השחרה':
                status_to_check = "BLACK"

            is_green = check_special(item.get('serial'), status_to_check)
            item['is_green'] = is_green
            item['action'] = action

            if is_green:
                current_count += 1

    new_status = 'טופל' if current_count >= total and total > 0 else 'בתהליך'

    if past_current != current_count and  current_count != total:
        special_logger.info(f"Request '{request_id}' is NOW {current_count}/{total} finished")
        print(f"Request '{request_id}' updated: {current_count}/{total}")

    if current_count >= total and total > 0 and row[4] != 'טופל':
        special_logger.info(f"SUCCESS: Request '{request_id}' is finished ({current_count}/{total})")

    if serials_raw == "[]":
        new_status = 'סורב'
        current_count = 0

    cursor.execute("UPDATE requests SET serials = ?, current = ?, status = ? WHERE id = ?",
                   (json.dumps(serials), current_count, new_status, request_id))
    conn.commit()
    conn.close()

@app.route('/get_all_requests_json')
@login_required
def get_all_requests_json():
    requests = get_all_special_requests()
    return jsonify({'requests': [dict(r) for r in requests]})

@app.route('/special_page', methods=["GET", "POST"])
@login_required
def special_page():
    user = get_current_user()
    all_special_requests = get_all_special_requests()

    product = None
    show_modal = False

    if request.method == "POST":
        serial = request.form.get("serialASK", "").strip()
        if serial:
            product = get_product_by_serial(serial)
            show_modal = True

    return render_template("special_page.html",
                           user=user,
                           all_special_requests=all_special_requests,
                           product=product,
                           show_modal=show_modal)

@app.route('/sign_page')
@login_required
def sign_page():
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

    conn = get_users_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users ORDER BY id")
    users_data = cursor.fetchall()
    conn.close()

    available_users = []
    for row in users_data:
        if row[1] != user.name:
            u = User(
                name=row[1], mador=row[2], id=row[0], password=row[3],
                type=row[4], is_active=bool(row[5]), is_admin=bool(row[6]),
                last_login=row[7], profile_image=row[8] if row[8] else "user_photo.png"
            )
            available_users.append(u)

    all_products = get_all_products_from_db()
    owned_products = [p for p in all_products if p.owner == user.name]
    all_return_items = [p for p in all_products if p.owner == 'מחסן']
    all_cities = sorted(list(set(p.city_name for p in all_products if p.city_name)))
    all_product_requests = get_all_product_requests_from_db()
    user_product_requests = [r for r in all_product_requests if r['user'] == user.name and r['to_user'] == 'מחסן']
    to_user_product_requests = [r for r in all_product_requests if r['to_user'] == user.name]
    pending_requests = [r for r in all_product_requests if r['status'] == 'ממתין' and r['user'] == user.name]
    available_names = [u.name for u in available_users]
    user_special_requests = [usr for usr in get_all_special_requests() if usr.ask_by == user.name]

    return render_template("sign_page.html", user=user, products=owned_products, remote_list_items=get_announcements(WAREHOUSE_FILE), all_retrun_items=all_return_items, all_cities=all_cities, user_product_requests=user_product_requests, to_user_product_requests=to_user_product_requests, available_names=available_names, pending_requests=pending_requests, user_special_requests=user_special_requests)

@app.route('/transfer_to_warehouse/<serial>', methods=['POST'])
@login_required
def transfer_to_warehouse(serial):
    conn = get_products_db()
    cursor = conn.cursor()
    user = get_current_user()

    # עדכון בעלות המוצר ל'מחסן'
    cursor.execute("UPDATE products SET owner = 'מחסן' WHERE serial = ?", (serial,))
    sign_logger.info(f"User '{user.name}' returned {serial} to warehouse")

    api_process_warehouse_transfer(serial, user.name)

    conn.commit()
    conn.close()
    return {"success": True}

@app.route('/remove_request/<request_id>', methods=['POST'])
@login_required
def remove_request(request_id):
    try:
        data = request.get_json()
        action = data.get('action')  # 'approve' או 'reject'

        with get_requests_db() as conn:
            cursor = conn.cursor()

            # 1. שליפת פרטי הבקשה
            cursor.execute("SELECT serial, to_user, user FROM product_requests WHERE id = ?", (request_id,))
            req = cursor.fetchone()

            if not req:
                return jsonify({'success': False, 'message': 'הבקשה לא נמצאה'}), 404

            serial = req[0]
            to_user = req[1]
            user = req[2]

            if action == 'approve':
                conn1 = get_products_db()
                cursor1 = conn1.cursor()
                cursor1.execute("UPDATE products SET owner = ? WHERE serial = ?", (to_user, serial))
                sign_logger.info(f"User '{user}' transferred the {serial} to User '{to_user}'")
                conn1.commit()
                api_update_process_users_transfer(serial, user, to_user)

                cursor.execute("UPDATE product_requests SET status = ? WHERE id = ?", ('אושר', request_id))
                conn.commit()
                return jsonify({'success': True, 'message': 'המוצר הועבר למשתמש בהצלחה'})

            elif action == 'reject':
                cursor.execute("UPDATE product_requests SET status = ? WHERE id = ?", ('סורב', request_id))
                conn.commit()
                return jsonify({'success': True, 'message': 'הבקשה סורבה'})
        return jsonify({'success': False, 'message': 'פעולה לא תקינה'})
    except Exception as e:
        print(f"Error processing request {request_id}: {e}")
        return jsonify({'success': False, 'message': 'שגיאת שרת פנימית'}), 500

@app.route('/request_product', methods=['POST'])
@login_required
def request_product():
    try:
        data = request.get_json()
        serial = data.get('serial')
        used_for = data.get('used_for')
        user = get_current_user()

        all_products = get_all_products_from_db()
        all_returned_serials = [p.serial for p in all_products if p.owner == 'מחסן']

        all_requested_serials = [rq['serial'] for rq in get_all_product_requests_from_db() if rq['user'] == user.name]
        all_requested = [rq for rq in get_all_product_requests_from_db() if rq['user'] == user.name]
        existing_request = next((rq for rq in all_requested if rq['serial'] == serial), None)

        if not serial or not used_for:
            return jsonify({'success': False, 'message': 'נא למלא את כל השדות'}), 400

        if serial not in all_returned_serials:
            return jsonify({'success': False, 'message': 'הסיראלי המבוקש אינו קיים'}), 400

        if serial in all_requested_serials and existing_request['status'] == 'ממתין':
            return jsonify({'success': False, 'message': 'הסיראלי הזה כבר נמצא בהליך בקשה'}), 400

        if used_for == "all":
            return jsonify({'success': False, 'message': 'נא לשייך בקשה רלוונטית שביקשת לבצע'}), 400

        user = get_current_user()

        with get_requests_db() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO product_requests (user, to_user, status, request_date, serial, used_for)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (user.name, "מחסן", "ממתין", datetime.now().strftime("%Y-%m-%d %H:%M:%S"), serial, used_for))
            conn.commit()
            request_warehouse_logger.info(f"User '{user.name}' request {serial} from warehouse")
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'message': 'שגיאת שרת פנימית'}), 500

@app.route('/send_product_to_user', methods=['POST'])
@login_required
def send_product_to_user():
    try:
        data = request.get_json()
        serial = data.get('serial')
        target_user = data.get('target_user')
        sender = get_current_user()

        if not serial or not target_user:
            return jsonify({'success': False, 'message': 'פרטים חסרים'}), 400

        with get_requests_db() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO product_requests (user, to_user, status, request_date, serial, used_for)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (sender.name, target_user, "ממתין", datetime.now().strftime("%Y-%m-%d %H:%M:%S"), serial, "העברה בין משתמשים"))
            conn.commit()

        return jsonify({'success': True})
    except Exception as e:
        print(f"Error: {e}")
        return jsonify({'success': False, 'message': 'שגיאת שרת פנימית'}), 500

def get_all_reports_from_db():
    reports_list = []

    try:
        conn = get_reports_db()
        conn.row_factory = sqlite3.Row  # מאפשר גישה לפי שם עמודה
        cursor = conn.cursor()

        # שאילתה שמאחדת את כל המידע הרלוונטי
        # אנחנו משתמשים ב-LEFT JOIN כדי לא לאבד דיווחים שאין להם הערות או קבצים
        query = """
        SELECT r.*, 
               (SELECT GROUP_CONCAT(content, '||') FROM report_notes WHERE report_id = r.id AND note_type = 'user_note') as notes_str,
               (SELECT GROUP_CONCAT(content, '||') FROM report_notes WHERE report_id = r.id AND note_type = 'admin_reply') as replies_str,
               (SELECT GROUP_CONCAT(file_path, '||') FROM report_files WHERE report_id = r.id) as files_str
        FROM reports r
        ORDER BY r.report_date DESC
        """

        cursor.execute(query)
        rows = cursor.fetchall()

        for row in rows:
            # המרת המחרוזות המחוברות חזרה לרשימות (אם הן קיימות)
            notes = row['notes_str'].split('||') if row['notes_str'] else None
            reply_notes = row['replies_str'].split('||') if row['replies_str'] else None
            report_files = row['files_str'].split('||') if row['files_str'] else []

            # יצירת אובייקט Report חדש
            report = Report(
                id=row['id'],
                written_by=row['written_by'],
                error_date=row['error_date'],
                report_title=row['report_title'],
                report_date=row['report_date'],
                notes=notes,
                report_status=row['report_status'],
                reply_notes=reply_notes,
                report_files=report_files,
                report_serials=row['report_serials'],
            )
            reports_list.append(report)

    except sqlite3.Error as e:
        print(f"Database error: {e}")
    finally:
        if conn:
            conn.close()

    return reports_list

@app.route('/report_page')
@login_required
def report_page():
    user = get_current_user()
    is_admin = user.is_admin
    editor = user.type == 1
    all_reports = get_all_reports_from_db()
    user_reports = [r for r in all_reports if r.written_by == user.name]

    tech_data = len([r for r in all_reports if r.report_title == "תקלה טכנית"])
    safety_data = len([r for r in all_reports if r.report_title == "דיווח בטיחות"])
    maint_data = len([r for r in all_reports if r.report_title == "תחזוקה מונעת"])
    other_data = len([r for r in all_reports if r.report_title == "אחר"])

    return render_template("report_page.html", user=user, all_reports=all_reports, user_reports=user_reports, is_admin=is_admin, editor=editor, tech_data=tech_data, safety_data=safety_data, maint_data=maint_data, other_data=other_data)

def update_product_reports(serial):
    conn = get_products_db()
    cursor = conn.cursor()

    cursor.execute("""
        UPDATE products 
        SET report_count = report_count + 1 
        WHERE serial = ?
    """, (serial,))

    conn.commit()
    conn.close()

@app.route('/create_report', methods=['POST'])
@login_required
def create_report():
    user = get_current_user()

    report_title = request.form.get('report_title')
    error_date = request.form.get('error_date')
    notes_content = request.form.get('notes')
    report_date_now = datetime.now().strftime('%Y-%m-%d %H:%M')
    report_serials_raw = request.form.get('error_serials') or ""

    files = request.files.getlist('report_files')
    file_paths_list = []

    conn = get_reports_db()
    cursor = conn.cursor()

    try:
        cursor.execute("""
            INSERT INTO reports (written_by, error_date, report_title, report_date, report_status, report_serials)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (user.name, error_date, report_title, report_date_now, "ממתין", report_serials_raw))

        report_id = cursor.lastrowid

        for file in files:
            if file and file.filename != '':
                filename = secure_filename(file.filename)
                unique_name = f"{report_id}_.{filename}"
                path = os.path.join(REPORT_FOLDER, unique_name)
                file.save(path)
                cursor.execute("INSERT INTO report_files (report_id, file_path) VALUES (?, ?)", (report_id, path))
                file_paths_list.append(path)

        if notes_content:
            cursor.execute("""
                INSERT INTO report_notes (report_id, content, note_type)
                VALUES (?, ?, 'user_note')
            """, (report_id, notes_content))

        if report_serials_raw.strip():
            serials_list = [s.strip() for s in report_serials_raw.split(',') if s.strip()]
            for serial in serials_list:
                update_product_reports(serial)

        conn.commit()
        flash('הדיווח נשלח בהצלחה', 'success')
    except Exception as e:
        if conn: conn.rollback()
        print(f"Error during report creation: {e}")
        flash(f'אירעה שגיאה: {e}', 'danger')
    finally:
        if conn: conn.close()

    return redirect(url_for('report_page'))

@app.route('/get_report_details/<int:report_id>')
@login_required
def get_report_details(report_id):
    conn = get_reports_db()
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # 1. שליפת הדיווח
    cursor.execute("SELECT * FROM reports WHERE id = ?", (report_id,))
    report = cursor.fetchone()

    if not report:
        conn.close()
        return jsonify({'error': 'דיווח לא נמצא'}), 404

    # 2. שליפת הערת המשתמש (התיאור המקורי)
    cursor.execute("SELECT content FROM report_notes WHERE report_id = ? AND note_type = 'user_note'", (report_id,))
    note_row = cursor.fetchone()
    user_note = note_row['content'] if note_row else "אין תיאור זמין"

    # --- התיקון כאן: שליפת תגובות המערכת (Admin Replies) ---
    cursor.execute("SELECT content FROM report_notes WHERE report_id = ? AND note_type = 'admin_reply'", (report_id,))
    # אנחנו אוספים את כל התגובות לרשימה
    reply_notes = [row['content'] for row in cursor.fetchall()]
    # -----------------------------------------------------

    # 3. שליפת נתיבי הקבצים
    cursor.execute("SELECT file_path FROM report_files WHERE report_id = ?", (report_id,))
    files = [row['file_path'] for row in cursor.fetchall()]

    conn.close()

    # 4. החזרת הנתונים
    return jsonify({
        'title': report['report_title'],
        'written_by': report['written_by'],
        'status': report['report_status'],
        'report_date': report['report_date'],
        'error_date': report['error_date'],
        'report_serials': report['report_serials'],
        'user_note': user_note,
        'reply_notes': reply_notes,
        'files': files
    })

def get_report_title(report_id):
    conn = get_reports_db()
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute("SELECT report_title FROM reports WHERE id = ?", (report_id,))
    report = cursor.fetchone()
    conn.close()

    if report:
        return report['report_title']
    return "דיווח לא נמצא"

def zero_product_reports(serial):
    conn = get_products_db()
    cursor = conn.cursor()

    cursor.execute("""
        UPDATE products 
        SET report_count = MAX(0, report_count - 1)
        WHERE serial = ?
    """, (serial,))

    conn.commit()
    conn.close()

@app.route('/delete_report/<int:report_id>', methods=['POST'])
@login_required
def delete_report(report_id):
    user = get_current_user()
    conn = get_reports_db()
    cursor = conn.cursor()

    try:
        # 1. שליפת פרטי הדיווח (כולל הסריאלים) לפני המחיקה
        cursor.execute("SELECT written_by, report_serials FROM reports WHERE id = ?", (report_id,))
        report = cursor.fetchone()

        if not report:
            return jsonify({'success': False, 'error': 'דיווח לא נמצא'}), 404

        if report[0] != user.name and not user.is_admin:
            return jsonify({'success': False, 'error': 'אין לך הרשאה למחוק דיווח זה'}), 403

        serials_string = report[1] or ""
        report_title = get_report_title(report_id)  # פונקציה קיימת שלך

        cursor.execute("SELECT file_path FROM report_files WHERE report_id = ?", (report_id,))
        files = cursor.fetchall()
        for file in files:
            file_path = file[0]
            if file_path and os.path.exists(file_path):
                try:
                    os.remove(file_path)
                except Exception as file_err:
                    print(f"Error deleting physical file {file_path}: {file_err}")

        cursor.execute("DELETE FROM report_files WHERE report_id = ?", (report_id,))
        cursor.execute("DELETE FROM report_notes WHERE report_id = ?", (report_id,))
        cursor.execute("DELETE FROM reports WHERE id = ?", (report_id,))

        if serials_string.strip():
            serials_list = [s.strip() for s in serials_string.split(',') if s.strip()]
            for sn in serials_list:
                zero_product_reports(sn)

        report_logger.info(f"User '{user.name}' deleted report ID {report_id} (Title: {report_title})")

        conn.commit()
        return jsonify({'success': True})

    except Exception as e:
        if conn:
            conn.rollback()
        print(f"Error deleting report: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500
    finally:
        if conn:
            conn.close()

@app.route('/add_admin_reply', methods=['POST'])
@login_required
def add_admin_reply():
    user = get_current_user()
    data = request.get_json()
    report_id = data.get('report_id')
    content = data.get('content')
    new_status = data.get('status')

    try:
        conn = get_reports_db()
        cursor = conn.cursor()

        cursor.execute("UPDATE reports SET report_status = ? WHERE id = ?", (new_status, report_id))

        cursor.execute("""
            INSERT INTO report_notes (report_id, content, note_type)
            VALUES (?, ?, 'admin_reply')
        """, (report_id, content))

        conn.commit()
        report_logger.info(f"A replay has added to report: {get_report_title(report_id)} by {user.name}")
        return jsonify({'success': True})
    except Exception as e:
        if conn: conn.rollback()
        return jsonify({'success': False, 'error': str(e)})
    finally:
        if conn: conn.close()

# ------------------ Run App ------------------
if __name__ == "__main__":
    app.run(debug=True)