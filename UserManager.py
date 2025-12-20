from User import User
import pandas as pd
from openpyxl import load_workbook

class UserManager:
    def __init__(self, excel_file):
        self.excel_file = excel_file
        self.users = []
        self.load_users_from_excel()

    def load_users_from_excel(self):
        """Load all users from the Excel file into memory."""
        try:
            self.users = []  # <-- Clear old users to avoid duplicates
            df = pd.read_excel(self.excel_file)
            # Strip spaces and lowercase column names for consistency
            df.columns = df.columns.str.strip().str.lower()

            for _, row in df.iterrows():
                user = User(
                    name=row.get('name'),
                    id=row.get('id'),
                    password=row.get('password'),
                    mador=row.get('mador'),
                    type=row.get('type'),
                    is_admin=row.get('is_admin', False),
                    is_active=row.get('is_active', True),
                    last_login=row.get('last_login', True)
                )
                self.users.append(user)
        except FileNotFoundError:
            print(f"File not found: {self.excel_file}")
        except Exception as e:
            print(f"Error reading Excel file: {e}")

    def find_user_by_name(self, name):
        """Find a user by username."""
        for user in self.users:
            if user.name == name:
                return user
        return None

    def find_user_by_id(self, id):
        """Find a user by ID."""
        for user in self.users:
            if user.id == id:
                return user
        return None

    def list_users(self):
        """Print all users."""
        for user in self.users:
            print(user)

    def find_user_in_row(self, username):
        """Find a user in Excel by row index."""
        df = pd.read_excel(self.excel_file)
        df.columns = df.columns.str.strip().str.lower()
        rows = df.index[df['name'].str.strip() == username].tolist()
        if not rows:
            return None, None
        return rows[0], df

    def save_users_to_excel(self):
        """Write all in-memory users to Excel."""
        data = []
        for u in self.users:
            data.append([
                u.name,
                u.mador,
                u.id,
                u.password,
                u.type,
                u.is_active,
                u.is_admin,
                u.last_login,
                u.profile_image
            ])
        df = pd.DataFrame(data, columns=['name', 'mador', 'id', 'password', 'type', 'is_active', 'is_admin', 'last_login', 'profile_image'])
        df.to_excel(self.excel_file, index=False)

    def add_user(self, user: User):
        """Add a new user and reload all users from Excel to refresh list."""
        # Append new user to Excel
        wb = load_workbook(self.excel_file)
        ws = wb.active
        ws.append([user.name, user.mador, user.id, user.password, user.type, user.is_active, user.is_admin, user.last_login])
        wb.save(self.excel_file)

        # Reload all users
        self.users = []
        self.load_users_from_excel()

    def remove_user(self, username):
        """Remove a user both from memory and Excel."""
        # Remove from memory
        self.users = [u for u in self.users if u.name != username]

        # Remove from Excel
        df = pd.read_excel(self.excel_file)
        df.columns = df.columns.str.strip().str.lower()
        df = df[df['name'].str.strip() != username]
        df.to_excel(self.excel_file, index=False)

