import mpv
import os
import sys
from datetime import datetime
from typing import Optional, Tuple
from dataclasses import dataclass

from .yaml import load_yaml_file
from .logger import MpvLogger
from .input import ReadInput
from .formatting import format_duration

OPTIONS_YAML_FILE = ".watch-options.yaml"


@dataclass
class Session:
    duration: Optional[int]
    position: Optional[float]


def _apply_watch_options(player, video_path) -> Tuple[Optional[str], Optional[str]]:
    run_before = None
    run_after = None

    video_dir = os.path.dirname(video_path)

    options = {}

    options_parent_path = os.path.join(video_dir, "..", OPTIONS_YAML_FILE)
    if os.path.isfile(options_parent_path):
        options.update(load_yaml_file(options_parent_path))

    options_path = os.path.join(video_dir, OPTIONS_YAML_FILE)
    if os.path.isfile(options_path):
        options.update(load_yaml_file(options_path))

    for opt_name, opt_val in options.items():
        if opt_name == "before":
            run_before = opt_val
        elif opt_name == "after":
            run_after = opt_val
        else:
            player[opt_name] = opt_val

    return run_before, run_after


def register_pause_handler(player):
    state = {"has_first": False}

    def pause_handler(named, value):
        if not state["has_first"]:
            state["has_first"] = True
        else:
            print("pause: " + ("paused" if value else "resumed"), flush=True)

    player.observe_property("pause", pause_handler)


def __log_position_events(player: mpv.MPV) -> None:
    last_pos = {"value": 0}

    @player.property_observer("time-pos")
    def time_observer(_name, value):
        if value is not None:
            rounded = round(value)
            diff = rounded - last_pos["value"]
            if abs(diff) >= 1:
                print("pos:", rounded, flush=True)
                last_pos["value"] = value


def watch_video(
    read_input: ReadInput,
    path: str,
    video_path: str,
    display_video: str,
    start_position: int,
    night_mode=False,
    sub_file=None,
    position_events=False,
) -> Optional[Tuple[int, str, datetime]]:
    logger = MpvLogger()
    player = mpv.MPV(
        log_handler=logger,
        input_default_bindings=True,
        input_vo_keyboard=True,
        fullscreen=True,
        osc=True,
    )
    if night_mode:
        # player['af'] = 'dynaudnorm=f=100:p=0.66'
        # player['af'] = 'dynaudnorm=f=150:g=15'
        player["af"] = "dynaudnorm"

    if sub_file:
        player["sub-files"] = sub_file

    session = Session(None, None)

    @player.on_key_press("Q")
    @player.on_key_press("q")
    def quit_binding():
        session.position = player.time_pos
        player.quit()

    if position_events:
        __log_position_events(player)

    run_before, run_after = _apply_watch_options(player, video_path)
    formatted_duration = None

    try:
        player.play(video_path)

        player.wait_until_playing()
        duration_obj = {}

        def set_duration(x):
            if x:
                duration_obj["value"] = x
                return True

        player.wait_for_property("duration", set_duration, False)
        duration = duration_obj["value"]

        # let the user know what they are watching before any other logs
        print(f"start: {video_path}", flush=True)

        formatted_duration = format_duration(duration)
        print(
            f"position: {format_duration(start_position)}/{formatted_duration}",
            flush=True,
        )
        logger.unsuspend()

        if run_before:
            os.system(run_before)

        session.duration = duration
        # once the duration has been read it seems to be safe to seek
        if start_position > 0:
            player.seek(start_position)

        player.show_text(
            display_video
            + " ("
            + format_duration(start_position)
            + " / "
            + formatted_duration
            + ")",
            2000,
        )

        register_pause_handler(player)
        if read_input.is_tty:
            read_input.start(lambda key: player.command("keypress", key))
        else:

            def read_non_tty_input(line: str):
                if len(line) == 1:
                    player.command("keypress", line)
                elif " " in line:
                    cmd, param = line.split(" ")
                    if cmd == "aid":
                        player["aid"] = param
                    elif cmd == "sid":
                        player["sid"] = param
                    else:
                        print(f"unrecognised command {cmd}", file=sys.stderr)
                else:
                    print(f"unrecognised input '{line}'", file=sys.stderr)

            read_input.start(read_non_tty_input)

        # wait for video to end
        try:
            player.wait_for_playback()
        except mpv.ShutdownError:
            pass

    finally:
        read_input.stop()
        if run_after:
            os.system(run_after)

    # process video finishing
    end_time = datetime.now()

    if session.position is None:
        session.position = session.duration

    # final status message
    print(flush=True)
    print(
        "end: "
        + format_duration(session.position)
        + "/"
        + format_duration(session.duration),
        flush=True,
    )

    return session.position, formatted_duration, end_time
