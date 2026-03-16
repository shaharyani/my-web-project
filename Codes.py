import json
import sqlite3

class Codes:
    def __init__(self, id, city_name: str, all_codes: list[str] = None):
        self.id = id
        self.city_name = city_name
        self.all_codes = all_codes if all_codes is not None else []

    def save_to_db(self):
        conn = sqlite3.connect('static/db/codes.db')
        cursor = conn.cursor()
        json_codes = json.dumps(self.all_codes)

        # שימוש ב-REPLACE כדי לעדכן אם העיר קיימת או להכניס אם לא
        cursor.execute("""
            INSERT OR REPLACE INTO city_codes (id, city_name, all_codes) 
            VALUES (
                (SELECT id FROM city_codes WHERE city_name = ?), 
                ?, 
                ?
            )
        """, (self.city_name, self.city_name, json_codes))

        conn.commit()
        conn.close()

    @staticmethod
    def get_codes_by_city(city_name):
        conn = sqlite3.connect('static/db/codes.db')
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT id, city_name, all_codes FROM city_codes WHERE city_name = ?", (city_name,))
        row = cursor.fetchone()
        conn.close()

        if row:
            codes_list = json.loads(row['all_codes']) if row['all_codes'] else []
            return Codes(id=row['id'], city_name=row['city_name'], all_codes=codes_list)
        return None

    @staticmethod
    def get_codes_by_city_list(city_name):
        """מחזירה רשימה שטוחה של קודים עבור עיר מסוימת"""
        conn = sqlite3.connect('static/db/codes.db')
        cursor = conn.cursor()

        try:
            cursor.execute("SELECT all_codes FROM city_codes WHERE city_name = ?", (city_name,))
            row = cursor.fetchone()

            if row and row[0]:
                # המרת ה-JSON מה-DB לרשימת Python
                return json.loads(row[0])
            return []  # אם העיר לא קיימת או שאין לה קודים

        except sqlite3.Error as e:
            print(f"שגיאה בשליפת רשימת קודים: {e}")
            return []
        finally:
            conn.close()

    @staticmethod
    def get_last_id():
        conn = sqlite3.connect('static/db/codes.db')
        cursor = conn.cursor()
        cursor.execute("SELECT MAX(id) FROM city_codes")
        result = cursor.fetchone()
        conn.close()
        return result[0] if result[0] is not None else 0

    @staticmethod
    def get_all_city_codes():
        """שולף את כל הערים והקודים מ-codes.db"""
        conn = sqlite3.connect('static/db/codes.db')
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT city_name, all_codes FROM city_codes")
        rows = cursor.fetchall()
        conn.close()

        # הפיכת הנתונים למילון ש-JavaScript יבין בקלות
        data = {}
        for row in rows:
            try:
                data[row['city_name']] = json.loads(row['all_codes'])
            except:
                data[row['city_name']] = []
        return data

    @staticmethod
    def is_code_globally_unique(code):
        """בודק אם הקוד קיים בתוך שדה ה-all_codes של עיר כלשהי"""
        conn = sqlite3.connect('static/db/codes.db')
        cursor = conn.cursor()
        # שליפת כל רשימות הקודים
        cursor.execute("SELECT all_codes FROM city_codes")
        rows = cursor.fetchall()
        conn.close()

        for row in rows:
            try:
                # טעינת ה-JSON של כל עיר ובדיקה אם הקוד שם
                codes_list = json.loads(row[0]) if row[0] else []
                if code in codes_list:
                    return False  # הקוד כבר קיים בעיר אחרת
            except:
                continue
        return True  # הקוד לא נמצא באף עיר