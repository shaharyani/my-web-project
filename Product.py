class Product:
    def __init__(self, serial: str, code:str, card_type:str, land_type:str, status:str, owner:str):
        self.serial = serial
        self.code = code
        self.card_type = card_type
        self.land_type = land_type
        self.status = status  # R - RED | B - BLACK | W - WHITE | N - NONE
        self.owner = owner

    def get_owner(self):
        return self.owner

    def get_serial(self):
        return self.serial

    def get_code(self):
        return self.code

    def getCardType(self):
        return self.card_type

    def getLandType(self):
        return self.land_type

    def __str__(self):
        return (f"Product(serial='{self.serial}', code='{self.code}', "
                f"card_type='{self.card_type}', land_type='{self.land_type}', "
                f"status='{self.status}', owner='{self.owner}')")