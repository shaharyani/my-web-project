import sqlite3

def get_users_db():
    return sqlite3.connect("users.db")

def get_logs_db():
    return sqlite3.connect("logs.db")
