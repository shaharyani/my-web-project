import os

ABS_PATH = r"C:\Users\shaha\PycharmProjects\PythonProjectWeb"

# PATH TO DATABASES
DB_FOLDER = os.path.join(ABS_PATH, "static", "db")
os.makedirs(DB_FOLDER, exist_ok=True)
USERS_DB = os.path.join(DB_FOLDER, "users.db")
PRODUCTS_DB = os.path.join(DB_FOLDER, "products.db")
TESTS_DB = os.path.join(DB_FOLDER, "tests.db")
CODES_DB = os.path.join(DB_FOLDER, "codes.db")
REPORTS_DB = os.path.join(DB_FOLDER, "reports.db")
REQUESTS_DB = os.path.join(DB_FOLDER, "requests.db")

# PATH TO DATA FILES
DATA_FILE = os.path.join(ABS_PATH, "static", "announcements.txt") # General announcements
WAREHOUSE_FILE = os.path.join(ABS_PATH, "static", "warehouse_data.txt") # Warehouse announcements

CITIES_PATH = r"C:\Users\shaha\Desktop\cities"
UPLOAD_FOLDER = os.path.join("static", "profile_pics")
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
REPORT_FOLDER = 'static/uploads/reports'

# PATH TO LOGS
LOG_FOLDER = os.path.join(ABS_PATH, "static", "logs")
os.makedirs(LOG_FOLDER, exist_ok=True)
LOG_FILE = os.path.join(LOG_FOLDER, "app.log")
LOG_TEST_FILE = os.path.join(LOG_FOLDER, "test.log")
LOG_SIGN_FILE = os.path.join(LOG_FOLDER, "sign.log")
LOG_REPORT_FILE = os.path.join(LOG_FOLDER, "report.log")
LOG_REQ_WAREHOUSE_FILE = os.path.join(LOG_FOLDER, "request_warehouse.log")
LOG_SPECIAL_FILE = os.path.join(LOG_FOLDER, "special.log")