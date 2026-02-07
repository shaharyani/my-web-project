import sqlite3

def get_users_db():
    return sqlite3.connect("users.db")

def get_products_db():
    conn = sqlite3.connect(
        "products.db",
        timeout=10,
        check_same_thread=False
    )
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA synchronous=NORMAL;")
    return conn

def get_tests_db():
    return sqlite3.connect(
        "tests.db",
        timeout=10,
    )

def get_codes_db():
    return sqlite3.connect(
        "codes.db",
        timeout=10,
    )
