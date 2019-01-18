class Task:
    def __init__(self, course_code, filter_func=None):
        self.course_code = course_code
        self.filter_func = filter_func
