class Product:
    def __init__(self, serial: str, code:str, card_number:int, land_number:str):
        self.serial = serial
        self.code = code
        self.card_number = card_number
        self.land_number = land_number

    def getProductSerial(self):
        return self.serial

    def getProductCode(self):
        return self.code

    def getProductCardNumber(self):
        return self.card_number

    def getProductLandNumber(self):
        return self.land_number