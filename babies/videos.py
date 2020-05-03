import mpv
import sys
import os
import re
from readchar import readchar
import termios
from threading import Thread
from datetime import datetime
from typing import Optional
from dataclasses import dataclass
import ffmpeg

from .db import Db
from .yaml import yaml, load_yaml_file

SHOW_EXTENSIONS = [
    'mkv',
    'avi',
    'mpg',
    'mp4',
    'mpeg',
    'ogv',
    'wmv',
    'flv',
    'm4v',
    'iso',
    'mov'
]

OPTIONS_YAML_FILE = '.watch-options.yaml'


@dataclass
class Session:
    duration: Optional[int]
    position: Optional[float]


def _log_mpv(loglevel, component, message):
    print('\r[{}] {}: {}'.format(loglevel, component, message))


def _path_to_video(db, path, ignore_errors=False, verbose=False):
    """
        If path is a directory then load series into db and return next
        unwatched show else return path to file
    """
    if os.path.isdir(path):
        try:
            db.load_series(path)
            video_entry = db.get_next_in_series()
            if not video_entry:
                raise ValueError('series is complete')
            video_path = os.path.join(path, video_entry['video'])
            return video_path, video_entry
        except FileNotFoundError:
            # if there is a single video in the directory then use it
            candidates = list(filter(_is_video, os.listdir(path)))
            candidate_count = len(candidates)
            if candidate_count == 0:
                raise ValueError(f'No videos found in directory {path}')
            elif candidate_count == 1:
                return os.path.join(path, candidates[0]), None
            else:
                # TODO: allow user to select with pager?
                raise ValueError('multiple candidates: ' + ', '.join(candidates))

    elif os.path.isfile(path):
        return path, None
    else:
        raise ValueError(f'No video found at {path}')


def _format_date(date):
    return str(date).replace('-', '/')


def _format_duration(duration):
    hours, min_secs = divmod(duration, 3600)
    mins, secs = divmod(min_secs, 60)
    fract = round((secs % 1) * 1000)

    def timecomp(comp):
        return str(round(comp)).zfill(2)

    return str(round(hours)) + ':' + timecomp(mins) + ':' + timecomp(secs) + '.' + str(fract)


def _format_time_with_duration(time, duration):
    return _format_date(time) + ' at ' + _format_duration(duration)


def _parse_duration(duration):
    hours, mins, secs = duration.split(':')
    print(duration, float(hours) * 3600 * float(mins) * 60 + float(secs))
    return float(hours) * 3600 + float(mins) * 60 + float(secs)


def _apply_watch_options(player, video_path) -> Optional[str]:
    run_after = None

    video_dir = os.path.dirname(video_path)

    options = {}

    options_parent_path = os.path.join(video_dir, '..', OPTIONS_YAML_FILE)
    if os.path.isfile(options_parent_path):
        options.update(load_yaml_file(options_parent_path))

    options_path = os.path.join(video_dir, OPTIONS_YAML_FILE)
    if os.path.isfile(options_path):
        options.update(load_yaml_file(options_path))

    for opt_name, opt_val in options.items():
        if opt_name == 'before':
            os.system(opt_val)
        elif opt_name == 'after':
            run_after = opt_val
        else:
            player[opt_name] = opt_val

    return run_after


def _read_keypresses(player):
    def readchars():
        while True:
            c = readchar()
            player.command('keypress', c)

    is_win = sys.platform in ('win32', 'cygwin')

    # backup stdin settings, readchar messes with them
    if not is_win:
        stdin_fd = sys.stdin.fileno()
        stdin_attr = termios.tcgetattr(stdin_fd)

    cmd_thread = Thread(target=readchars)
    cmd_thread.daemon = True
    cmd_thread.start()

    def cleanup():
        # see above
        if not is_win:
            termios.tcsetattr(stdin_fd, termios.TCSADRAIN, stdin_attr)
        # readchar blocks this, see daemon use above
        # cmd_thread.join()

    return cleanup


def _is_video(path):
    for suffix in SHOW_EXTENSIONS:
        if path.endswith('.' + suffix):
            return True
    return False


def display_videos(paths, ignore_errors=False, verbose=False):
    db = Db()
    logs = []

    for path in paths:
        try:
            video_path, _ = _path_to_video(db, path, ignore_errors=ignore_errors, verbose=verbose)
            filename = os.path.basename(video_path)

            if verbose:
                logs.append({
                    'path': path,
                    'filename': filename
                })
            else:
                logs.append(filename)
        except ValueError as e:
            if not ignore_errors:
                raise e

    if verbose:
        yaml.dump(logs, sys.stdout)
    else:
        for log in logs:
            print(log)


def record_video(path, comment):
    db = Db()
    video_path, video_entry = _path_to_video(db, path)
    duration = _format_duration(float(ffmpeg.probe(video_path)['format']['duration']))

    video_filename = os.path.basename(video_path)
    start = 'unknown at ' + _format_duration(0)
    end = 'unknown at ' + duration
    db.append_global_record({
        'video': video_filename,
        'duration': duration,
        'start': start,
        'end': end,
        'comment': comment,
    })
    print('recorded ' + video_filename + ' in global log with comment: ' + comment)

    if video_entry:
        video_entry['duration'] = duration
        viewings = video_entry.setdefault('viewings', [])
        viewings.append({'start': start, 'end': end, 'comment': comment})
        db.write_series(path)
        print('recorded ' + video_filename + ' in series log with comment: ' + comment)


def watch_video(path, dont_record, night_mode, sub_file):
    player = mpv.MPV(log_handler=_log_mpv, input_default_bindings=True, input_vo_keyboard=True, fullscreen=True, osc=True)
    if night_mode:
        # player['af'] = 'dynaudnorm=f=100:p=0.66'
        # player['af'] = 'dynaudnorm=f=150:g=15'
        player['af'] = 'dynaudnorm'

    if sub_file:
        player['sub-files'] = sub_file

    session = Session(None, None)

    @player.on_key_press('Q')
    @player.on_key_press('q')
    def quit_binding():
        session.position = player.time_pos
        player.quit()

    db = Db()
    video_path, video_entry = _path_to_video(db, path)

    run_after = _apply_watch_options(player, video_path)

    start_time = datetime.now()
    player.play(video_path)
    viewings = video_entry and video_entry.get('viewings', None)

    # get duration of video
    def set_duration(x):
        if x:
            session.duration = x
            return True
    player.wait_for_property('duration', set_duration, False)

    start_position = 0
    # once the duration has been read it seems to be safe to seek
    if viewings:
        final_viewing = viewings[-1]['end'].split(' at ')[1]
        start_position = _parse_duration(final_viewing)
        player.seek(start_position)

    video_filename = os.path.basename(video_path)
    duration = _format_duration(session.duration)

    player.show_text(video_filename + ' (' + _format_duration(start_position) + ' / ' + duration + ')' , 2000)

    cleanup_key_handler = None
    if sys.stdin.isatty():
        cleanup_key_handler = _read_keypresses(player)

    # wait for video to end
    player.wait_for_playback()

    if run_after:
        os.system(run_after)

    if cleanup_key_handler:
        cleanup_key_handler()

    # process video finishing
    end_time = datetime.now()

    if session.position is None:
        session.position = session.duration

    if not dont_record:
        start = _format_time_with_duration(start_time, start_position)
        end = _format_time_with_duration(end_time, session.position)

        # append the global record first in case the series update fails due to full
        # disk or readonly mount etc.
        db.append_global_record({
            'video': video_filename,
            'duration': duration,
            'start': start,
            'end': end,
        })
        print('recorded video in global record:', video_filename)

        if video_entry:
            if video_entry.get('duration', None) != duration:
                video_entry['duration'] = duration
            viewings = video_entry.setdefault('viewings', [])

            viewings.append({'start': start, 'end': end})
            db.write_series(path)
            print('recorded video in series record:', video_filename)


def create_show_db(dirpath, force):
    db = Db()

    # TODO: merge new content with old content instead
    if not force and os.path.isfile(Db.get_series_db_path(dirpath)):
        raise ValueError('series record already exists')

    for filename in sorted(os.listdir(dirpath)):
        if _is_video(filename):
            db.add_show_to_series({'video': filename})

    db.write_series(dirpath)


def grep_show_record(terms, quiet):
    db = Db()
    db.load_global_record()
    matches = db.filter_global_record(
        lambda record: all(re.search(term, record['video'], re.IGNORECASE) for term in terms)
    )

    if quiet:
        print('\n'.join(list(map(lambda m: m['video'], matches))))
    else:
        yaml.dump(list(matches), sys.stdout)
