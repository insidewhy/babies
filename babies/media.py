from .videos import watch_video
from .spotify import listen_to_track
from .input import ReadInput


def play_media(
    read_input: ReadInput,
    uri: str,
    dont_record=False,
    night_mode=False,
    sub_file=None,
    comment=None,
    title=None,
):
    if uri.startswith("spotify:"):
        listen_to_track(read_input, uri)
    else:
        watch_video(
            read_input,
            uri,
            dont_record=dont_record,
            night_mode=night_mode,
            sub_file=sub_file,
            comment=comment,
            title=title,
        )

