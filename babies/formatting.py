from math import floor


def format_duration(duration):
    hours, min_secs = divmod(duration, 3600)
    mins, secs = divmod(min_secs, 60)
    fract = floor((secs % 1) * 1000)

    def timecomp(comp):
        return str(floor(comp)).zfill(2)

    return (
        str(floor(hours))
        + ":"
        + timecomp(mins)
        + ":"
        + timecomp(secs)
        + "."
        + str(fract)
    )


def format_date(date):
    return str(date).replace("-", "/")


def format_time_with_duration(time, duration):
    return format_date(time) + " at " + format_duration(duration)
