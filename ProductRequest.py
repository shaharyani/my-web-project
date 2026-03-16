class ProductRequest:
    def __init__(self, id, status, from_user, to_user, request_date, serial, used_for):
        self.id = id
        self.user = from_user
        self.to_user = to_user if to_user is not None else "מחסן"
        self.status = status if status else "ממתין" # סורב | אושר | ממתין
        self.request_date = request_date
        self.serial = serial
        self.used_for = used_for

    def to_dict(self):
        """הופך את האובייקט למילון עבור שליפה קלה ל-SQL או JSON"""
        return {
            "id": self.id,
            "user": self.user,
            "to_user": self.to_user,
            "status": self.status,
            "request_date": self.request_date,
            "serial": self.serial,
            "used_for": self.used_for
        }