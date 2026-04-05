from typing import List

class Product:
    def __init__(self, id: int, serial: str, code: str, land_type: str, city_name: str, status: str, owner: str, notes: List[str], reports_count: int, count: int):
        self.id = id
        self.serial = serial
        self.code = code
        self.land_type = land_type
        self.city_name = city_name
        self.status = status  # R | B | W | N
        self.owner = owner
        self.notes = notes or []
        self.reports_count = reports_count
        self.count = count

    def __str__(self):
        return (f"Product(id={self.id}, serial='{self.serial}', city='{self.city_name}', "
                f"status='{self.status}', current_code='{self.code}', notes={self.notes}), reports_count={self.reports_count}, count={self.count})")
