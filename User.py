class User:
    def __init__(self, name:str, mador:str, id:int, password:str,type:int, is_active:bool, is_admin:bool, last_login:str, profile_image="user_photo.png"):
        self.name = name
        self.mador = mador
        self.id = id
        self.password = password  # private-like convention with "_"
        self.type = type  # private-like convention with "_"
        self.is_active = is_active
        self.is_admin = is_admin
        self.last_login = last_login
        self.profile_image = profile_image

    def check_password(self, new_password):
        """Check if the provided password matches the stored one."""
        return self.password == new_password

    def get_name(self):
        return self.name

    def deactivate(self):
        """Deactivate the user account."""
        self.is_active = False

    def activate(self):
        """Activate the user account."""
        self.is_active = True

    def admin_check(self):
        return self.is_admin

    def set_password(self, new_password):
        """Set new password."""
        self.password = new_password

    def get_password(self):
        """Get the stored password."""
        return self.password

    def set_last_login(self, new_last_login):
        """Set the last login date."""
        self.last_login = new_last_login

    def get_last_login(self):
        """Get the last login date."""
        return self.last_login

    def __str__(self):
        return f"User(name='{self.name}', id='{self.id}', mador='{self.mador}', type='{self.type}' password='{self.password}', active={self.is_active}, admin='{self.is_admin}, last_login={self.last_login})')"
