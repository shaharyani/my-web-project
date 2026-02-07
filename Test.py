class Test:
    def __init__(self, id, serial, test_level, checked_by, is_passed, excel_str_file, is_verified):
        self.id = id
        self.serial = serial
        self.test_level = test_level
        self.checked_by = checked_by
        self.is_passed = bool(is_passed)
        self.excel_str_file = excel_str_file
        self.is_verified = bool(is_verified)

    @property
    def formatted_date(self):
        # עכשיו self מועבר בצורה תקינה
        return self.extract_test_date(self.excel_str_file)

    @property
    def test_name(self):
        # עכשיו self מועבר בצורה תקינה
        return self.extract_test_name(self.excel_str_file)

    # הוספת self לפרמטרים של הפונקציה
    def extract_test_date(self, filename):
        if not filename: return ""
        base_name = filename.split('_')[0]
        date_part = base_name[-14:]

        # בניית המחרוזת בצורה בטוחה
        if len(date_part) < 14: return "תאריך לא תקין"

        formatted_date = f"{date_part[0:2]}/{date_part[2:4]}/{date_part[4:8]} {date_part[8:10]}:{date_part[10:12]}:{date_part[12:14]}"
        return formatted_date

    # הוספת self לפרמטרים של הפונקציה
    def extract_test_name(self, filename):
        if not filename: return "UNKNOWN"
        name_without_ext = filename.replace('.txt', '')
        if '_' in name_without_ext:
            return name_without_ext.split('_')[1]
        return "UNKNOWN_TEST"