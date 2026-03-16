from static.helper.db import get_users_db, get_products_db, get_tests_db, get_codes_db, get_reports_db, get_requests_db

def create_all_dbs():
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
        profile_image TEXT DEFAULT 'user_photo.png',
        email TEXT
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
            code TEXT UNIQUE NOT NULL,
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

    conn4 = get_reports_db()
    cursor = conn4.cursor()
    cursor.execute("PRAGMA foreign_keys = ON;")

    # שימוש ב-executescript כדי להריץ את כל הפקודות יחד
    cursor.executescript("""
        CREATE TABLE IF NOT EXISTS reports (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            written_by TEXT NOT NULL,
            error_date TEXT,
            report_title TEXT,
            report_date TEXT DEFAULT (datetime('now', 'localtime')),
            report_status TEXT DEFAULT 'ממתין'
        );
    
        CREATE TABLE IF NOT EXISTS report_notes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            report_id INTEGER NOT NULL,
            content TEXT NOT NULL,
            note_type TEXT NOT NULL, -- 'user_note' או 'admin_reply'
            FOREIGN KEY (report_id) REFERENCES reports (id) ON DELETE CASCADE
        );
    
        CREATE TABLE IF NOT EXISTS report_files (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            report_id INTEGER NOT NULL,
            file_path TEXT NOT NULL,
            FOREIGN KEY (report_id) REFERENCES reports (id) ON DELETE CASCADE
        );
    """)

    conn4.commit()
    conn4.close()

    conn5 = get_requests_db()
    cursor = conn5.cursor()
    cursor.execute("PRAGMA foreign_keys = ON;")

    cursor.executescript("""
        -- טבלה עבור ProductRequest
        CREATE TABLE IF NOT EXISTS product_requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user TEXT NOT NULL,
            to_user TEXT DEFAULT 'מחסן',
            status TEXT DEFAULT 'ממתין',
            request_date TEXT,
            serial TEXT NOT NULL,
            used_for TEXT
        );
    
        -- טבלה עבור Request (הבקשות הכלליות)
        CREATE TABLE IF NOT EXISTS requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            target TEXT,
            description TEXT,
            ask_by TEXT,
            serials TEXT, -- נשמור רשימת סריאלים מופרדת בפסיקים [cite: 35]
            finish_date TEXT,
            request_date TEXT, 
            status TEXT,
            total INTEGER,
            current INTEGER
        );
    
        -- טבלה חדשה עבור משתמשים מורשי מיוחדים (users_group)
        CREATE TABLE IF NOT EXISTS special_users (
            username TEXT PRIMARY KEY
        );
    """)

    conn5.commit()
    conn5.close()