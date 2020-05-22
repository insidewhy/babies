import mpv
import os
from threading import Thread, Condition
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


def _wait_for_duration_or_terminate(player):
    done_condition = Condition()
    data = {}

    # get duration of video
    def wait_for_duration():
        def set_duration(x):
            if x:
                data["duration"] = x
                return True

        player.wait_for_property("duration", set_duration, False)
        with done_condition:
            done_condition.notify_all()

    def wait_for_playback():
        player.wait_for_playback()
        with done_condition:
            done_condition.notify_all()

    duration_thread = Thread(target=wait_for_duration)
    playback_thread = Thread(target=wait_for_playback)
    duration_thread.daemon = True
    duration_thread.start()
    playback_thread.start()

    with done_condition:
        done_condition.wait()
        return data.get("duration")


def register_pause_handler(player):
    state = {"has_first": False}

    def pause_handler(named, value):
        if not state["has_first"]:
            state["has_first"] = True
        else:
            print("pause: " + ("paused" if value else "resumed"), flush=True)

    player.observe_property("pause", pause_handler)


def watch_video(
    read_input: ReadInput,
    path: str,
    video_path: str,
    display_video: str,
    start_position: int,
    night_mode=False,
    sub_file=None,
):
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

    run_before, run_after = _apply_watch_options(player, video_path)
    formatted_duration = None

    try:
        player.play(video_path)
        duration = _wait_for_duration_or_terminate(player)
        if not duration:
            return

        # let the user know what they are watching before any other logs
        print(f"start: {video_path}", flush=True)
        logger.unsuspend()

        if run_before:
            os.system(run_before)

        session.duration = duration
        # once the duration has been read it seems to be safe to seek
        if start_position > 0:
            player.seek(start_position)

        formatted_duration = format_duration(session.duration)

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
        read_input.start(lambda key: player.command("keypress", key))

        # wait for video to end
        player.wait_for_playback()

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
