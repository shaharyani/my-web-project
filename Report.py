class Report:
    def __init__(self, id, written_by, error_date, report_date, report_title, notes, report_status, reply_notes, report_files):
        self.id = id
        self.written_by = written_by
        self.error_date = error_date
        self.report_title = report_title
        self.report_date = report_date
        self.notes = notes if notes else None
        self.report_status = report_status if report_status else "ממתין" # ממתין | טופל
        self.reply_notes = reply_notes if reply_notes else None
        self.report_files = report_files