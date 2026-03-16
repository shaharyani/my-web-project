import sqlite3

from static.helper.AppContns import USERS_DB, PRODUCTS_DB, TESTS_DB, CODES_DB, REPORTS_DB, REQUESTS_DB


def get_users_db():
    return sqlite3.connect(USERS_DB)

def get_products_db():
    conn = sqlite3.connect(
        PRODUCTS_DB,
        timeout=10,
        check_same_thread=False
    )
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA synchronous=NORMAL;")
    return conn

def get_tests_db():
    return sqlite3.connect(
        TESTS_DB,
        timeout=10,
    )

def get_codes_db():
    return sqlite3.connect(
        CODES_DB,
        timeout=10,
    )

def get_reports_db():
    return sqlite3.connect(
        REPORTS_DB,
        timeout=10,
    )

def get_requests_db():
    return sqlite3.connect(
        REQUESTS_DB,
        timeout=10,
    )