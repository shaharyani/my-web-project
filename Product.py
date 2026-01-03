from typing import List

class Product:
    def __init__(self, id: int, serial: str, code: str, land_type: str, city_name: str, status: str, owner: str, notes: List[str]):
        self.id = id
        self.serial = serial
        self.code = code
        self.land_type = land_type
        self.city_name = city_name
        self.status = status  # R | B | W | N
        self.owner = owner
        self.notes = notes or []

    def __str__(self):
        return (f"Product(id={self.id}, serial='{self.serial}', code='{self.code}', "
                f"land_type='{self.land_type}', city_name='{self.city_name}', "
                f"status='{self.status}', owner='{self.owner}', note='{self.notes}')")
