import sqlite3

def get_users_db():
    return sqlite3.connect("users.db")

def get_products_db():
    return sqlite3.connect("products.db")
