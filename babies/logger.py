import re
from sys import stderr, stdout


class MpvLogger:
    def __init__(self):
        self.suspended = True
        self.suspended_logs = []

    def __call__(self, log_level, component, message: str):
        # hide empty cplayer messages
        if component == "cplayer" and not message:
            return

        if "--sid" in message:
            sub_code = re.sub(".*--sid=(\\d+).*'(.*)'.*", "\\1,\\2", message)
            if "(+)" in message:
                print("active-sub:", sub_code)
            else:
                print("sub:", sub_code)
        elif "--aid" in message:
            aid = re.sub(".*--aid=(\\d+).*--alang=([^\\s]+).*", "\\1,\\2", message)
            if "(+)" in message:
                print("active-audio:", aid)
            else:
                print("audio:", aid)
        else:
            formatted_message = "[{}] {}: {}".format(log_level, component, message)
            is_error = log_level == "error"
            if self.suspended and not is_error:
                self.suspended_logs.append(formatted_message)
            else:
                print(formatted_message, file=stderr if is_error else stdout)

    def unsuspend(self):
        self.suspended = False
        for log in self.suspended_logs:
            print(log)
