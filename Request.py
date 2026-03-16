global users_group
class Request:

    def __init__(self, id, title, target, description, ask_by, serials, finish_date, request_date, status, total, current):
        self.id = id
        self.title = title
        self.target = target
        self.description = description
        self.ask_by = ask_by
        self.serials = serials
        self.finish_date = finish_date
        self.request_date = request_date
        self.status = status
        self.total = total
        self.current = current