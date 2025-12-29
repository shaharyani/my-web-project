import sqlite3

from werkzeug.security import generate_password_hash, check_password_hash
from db import get_users_db

class User:
    def __init__(self, id: int, name: str, mador: str, password: str, type: int,
                 is_active: bool, is_admin: bool, last_login: str, profile_image="user_photo.png"):
        self.id = id
        self.name = name
        self.mador = mador
        self.password = password  # already hashed from DB or generate new
        self.type = type
        self.is_active = is_active
        self.is_admin = is_admin
        self.last_login = last_login
        self.profile_image = profile_image

    def get_name(self):
        return self.name

    def get_mador(self):
        return self.mador

    # --- Password ---
    def check_password(self, password):
        return check_password_hash(self.password, password)

    def set_password(self, new_password):
        self.password = generate_password_hash(new_password)
        self.update_db_field("password", self.password)

    # --- Last login ---
    def set_last_login(self, new_last_login):
        self.last_login = new_last_login
        self.update_db_field("last_login", self.last_login)

    # --- Account status ---
    def deactivate(self):
        self.is_active = False
        self.update_db_field("is_active", 0)

    def activate(self):
        self.is_active = True
        self.update_db_field("is_active", 1)

    # --- Admin check ---
    def admin_check(self):
        return self.is_admin

    # --- DB helper ---
    def update_db_field(self, field, value):
        conn = get_users_db()
        cursor = conn.cursor()
        cursor.execute(f"UPDATE users SET {field}=? WHERE id=?", (value, self.id))
        conn.commit()
        conn.close()

    # --- Representation ---
    def __str__(self):
        return f"User(name='{self.name}', id={self.id}, mador='{self.mador}', type={self.type}, active={self.is_active}, admin={self.is_admin}, last_login={self.last_login})"

    @classmethod
    def get_by_id(cls, user_id):
        conn = get_users_db()
        conn.row_factory = sqlite3.Row  # <-- important!
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE id=?", (user_id,))
        row = cursor.fetchone()
        conn.close()
        if row:
            return cls(**dict(row))  # convert sqlite3.Row to dict
        return None

    @classmethod
    def get_by_name(cls, name):
        conn = get_users_db()
        conn.row_factory = sqlite3.Row  # <-- important!
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE name=?", (name,))
        row = cursor.fetchone()
        conn.close()
        if row:
            return cls(**dict(row))  # convert sqlite3.Row to dict
        return None

    @classmethod
    def create(cls, name, mador, password, type=1, is_active=True, is_admin=False, last_login="", profile_image="user_photo.png"):
        hashed = generate_password_hash(password)
        conn = get_users_db()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO users (name, mador, password, type, is_active, is_admin, last_login, profile_image)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (name, mador, hashed, type, int(is_active), int(is_admin), last_login, profile_image))
        conn.commit()
        user_id = cursor.lastrowid
        conn.close()
        return cls.get_by_id(user_id)
