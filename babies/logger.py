from sys import stderr, stdout

class MpvLogger:
    def __init__(self):
        self.suspended = True
        self.suspended_logs = []

    def __call__(self, log_level, component, message):
        # hide empty cplayer messages
        if component == 'cplayer' and not message:
            return

        formatted_message = '[{}] {}: {}'.format(log_level, component, message)
        is_error = log_level == 'error'
        if self.suspended and not is_error:
            self.suspended_logs.append(formatted_message)
        else:
            print(formatted_message, file=stderr if is_error else stdout)

    def unsuspend(self):
        self.suspended = False
        for log in self.suspended_logs:
            print(log)
