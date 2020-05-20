import mpv
import sys
import os
import re
from threading import Thread, Condition
from datetime import datetime
from typing import Optional, Tuple
from dataclasses import dataclass
from math import floor
import ffmpeg

from .db import Db
from .yaml import yaml, load_yaml_file
from .logger import MpvLogger
from .input import read_keypresses

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


def _is_url(path: str) -> bool:
    return path.startswith('https://') or path.startswith('http://')


def _find_candidate_in_directory(path: str) -> str:
    # if there is a single video in the directory then use it
    candidates = list(filter(_is_video, os.listdir(path)))
    candidate_count = len(candidates)
    if candidate_count == 0:
        raise ValueError(f'No videos found in directory {path}')
    elif candidate_count == 1:
        return os.path.join(path, candidates[0])
    else:
        # TODO: allow user to select with pager?
        raise ValueError('multiple candidates: ' + ', '.join(candidates))


def _path_to_video(db, path, ignore_errors=False, verbose=False):
    """
        If path is a directory then load series into db and return next
        unwatched show else return path to file
    """
    if _is_url(path):
        return path, None, None
    elif os.path.isdir(path):
        if db.load_series(path):
            video_entry = db.get_next_in_series()
            if not video_entry:
                raise ValueError('series is complete')

            alias = video_entry.get('alias', None)
            aliased_db = None
            if alias:
                aliased_db = Db()
                aliased_db.load_series(alias)

            video = video_entry['video']
            if _is_url(video):
                video_path = video
            elif alias:
                video_path = os.path.join(path, alias, video)
            else:
                video_path = os.path.join(path, video)

            return video_path, video_entry, aliased_db
        else:
            return _find_candidate_in_directory(path), None, None

    elif os.path.isfile(path):
        return path, None, None
    else:
        raise ValueError(f'No video found at {path}')


def _format_date(date):
    return str(date).replace('-', '/')


def _format_duration(duration):
    hours, min_secs = divmod(duration, 3600)
    mins, secs = divmod(min_secs, 60)
    fract = floor((secs % 1) * 1000)

    def timecomp(comp):
        return str(floor(comp)).zfill(2)

    return str(floor(hours)) + ':' + timecomp(mins) + ':' + timecomp(secs) + '.' + str(fract)


def _format_time_with_duration(time, duration):
    return _format_date(time) + ' at ' + _format_duration(duration)


def _parse_duration(duration):
    hours, mins, secs = duration.split(':')
    return float(hours) * 3600 + float(mins) * 60 + float(secs)


def _apply_watch_options(player, video_path) -> Tuple[Optional[str], Optional[str]]:
    run_before = None
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
            run_before = opt_val
        elif opt_name == 'after':
            run_after = opt_val
        else:
            player[opt_name] = opt_val

    return run_before, run_after


def _is_video(path):
    for suffix in SHOW_EXTENSIONS:
        if path.endswith('.' + suffix):
            return True
    return False


def display_videos(paths, ignore_errors=False, verbose=False, no_extension_filter=False):
    db = Db()
    logs = []

    for path in paths:
        try:
            video_path, _, _ = _path_to_video(db, path, ignore_errors=ignore_errors, verbose=verbose)
            if not no_extension_filter and not _is_video(video_path):
                continue

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


def get_video_entry_for_log(video_path: str) -> str:
    return video_path if _is_url(video_path) else os.path.basename(video_path)


def record_video(path, comment):
    db = Db()
    video_path, video_entry, _ = _path_to_video(db, path)
    duration = _format_duration(float(ffmpeg.probe(video_path)['format']['duration']))

    video_filename = get_video_entry_for_log(video_path)
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


def _wait_for_duration_or_terminate(player):
    done_condition = Condition()
    data = {}

    # get duration of video
    def wait_for_duration():
        def set_duration(x):
            if x:
                data['duration'] = x
                return True
        player.wait_for_property('duration', set_duration, False)
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
        return data.get('duration')


def register_pause_handler(player):
    state = { 'has_first': False }
    def pause_handler(named, value):
        if not state['has_first']:
            state['has_first'] = True
        else:
            print('pause: ' + ('paused' if value else 'resumed'), end="\r\n", flush=True)
    player.observe_property('pause', pause_handler)


def watch_video(path, dont_record, night_mode, sub_file=None, comment=None, title=None):
    logger = MpvLogger()
    player = mpv.MPV(
        log_handler=logger,
        input_default_bindings=True,
        input_vo_keyboard=True,
        fullscreen=True,
        osc=True
    )
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
    video_path, video_entry, aliased_db = _path_to_video(db, path)
    run_before, run_after = _apply_watch_options(player, video_path)

    start_time = datetime.now()
    cleanup_key_handler = None

    try:
        player.play(video_path)
        viewings = video_entry and video_entry.get('viewings', None)

        duration = _wait_for_duration_or_terminate(player)
        if not duration:
            return

        # let the user know what they are watching before any other logs
        print(f"start: {video_path}", flush=True)
        logger.unsuspend()

        if run_before:
            os.system(run_before)

        session.duration = duration
        start_position = 0
        # once the duration has been read it seems to be safe to seek
        if viewings:
            final_viewing = viewings[-1]['end'].split(' at ')[1]
            start_position = _parse_duration(final_viewing)
            player.seek(start_position)

        video_filename = get_video_entry_for_log(video_path)
        duration = _format_duration(session.duration)

        player.show_text(video_filename + ' (' + _format_duration(start_position) + ' / ' + duration + ')' , 2000)

        register_pause_handler(player)
        cleanup_key_handler = read_keypresses(lambda key: player.command('keypress', key))

        # wait for video to end
        player.wait_for_playback()

    finally:
        if run_after:
            os.system(run_after)

        if cleanup_key_handler:
            cleanup_key_handler()

    # process video finishing
    end_time = datetime.now()

    if session.position is None:
        session.position = session.duration

    # final status message
    print(flush=True)
    print(
        "end: " + _format_duration(session.position) + '/' + _format_duration(session.duration),
        flush=True
    )

    if not dont_record:
        start = _format_time_with_duration(start_time, start_position)
        end = _format_time_with_duration(end_time, session.position)

        record = {
            'video': video_filename,
            'duration': duration,
            'start': start,
            'end': end,
        }
        if comment:
            record['comment'] = comment
        elif video_entry and 'comment' in video_entry:
            record['comment'] = video_entry['comment']

        if title:
            record['title'] = title
        elif video_entry and 'title' in video_entry:
            record['title'] = video_entry['title']

        # append the global record first in case the series update fails due to full
        # disk or readonly mount etc.
        db.append_global_record(record)
        print('recorded video in global record:', video_filename)

        if video_entry:
            # reload database in case something was enqueued while the video
            # was being watched
            db.load_series(path)
            video_entry_backup = video_entry
            video_entry = db.get_next_in_series()
            if not video_entry or video_entry['video'] != video_entry_backup['video']:
                print(
                    'Something changed while watching video, not recording entry in series record',
                    file=sys.stderr
                )
                return

            if video_entry.get('duration', None) != duration:
                video_entry['duration'] = duration
            if comment:
                video_entry['comment'] = comment
            if title:
                video_entry['title'] = title
            viewings = video_entry.setdefault('viewings', [])

            viewings.append({'start': start, 'end': end})
            db.write_series(path)
            print('recorded video in series record:', video_filename)

            if aliased_db:
                # TODO: reload aliased_db in case it has changed?
                next_aliased_entry = aliased_db.get_next_in_series()
                if next_aliased_entry['video'] == video_entry['video']:
                    next_aliased_entry['duration'] = duration
                    aliased_viewings = next_aliased_entry.setdefault('viewings', [])
                    aliased_viewings.append({'start': start, 'end': end})
                    aliased_path = video_entry['alias']
                    aliased_db.write_series(aliased_path)
                    print('recorded video in aliased series record:', aliased_path)


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
    matches = db.get_matching_entries(
        lambda record: all(re.search(term, record['video'], re.IGNORECASE) for term in terms)
    )

    if quiet:
        print('\n'.join(list(map(lambda m: m['video'], matches))))
    else:
        yaml.dump(list(matches), sys.stdout)

def enqueue_videos(queue_path, paths, comment=None, prune=False, title=None):
    db = Db()
    db.load_series(queue_path)
    new_entries = []
    queued_videos = db.get_series_video_set()

    if prune:
        db.prune_watched()

    entry_template = {}
    if comment:
        entry_template['comment'] = comment
    if title:
        entry_template['title'] = title

    def add_new_entry(video, alias=None):
        # don't allow duplicates
        if video not in queued_videos:
            entry = entry_template.copy()
            entry['video'] = video
            if alias:
                entry['alias'] = alias
            new_entries.append(entry)
            queued_videos.add(video)
            db.add_show_to_series(entry)

    for path in paths:
        if _is_url(path) or _is_video(path):
            add_new_entry(path)
        elif os.path.isdir(path):
            series_db = Db()
            if series_db.load_series(path):
                # TODO: skip entries that are already enqueued, e.g.
                # first queue episode 1, then episode 2
                next_entry = series_db.get_next_in_series()
                if next_entry and 'alias' not in next_entry:
                    add_new_entry(next_entry['video'], path)
            else:
                video = _find_candidate_in_directory(path)
                add_new_entry(video)

    if new_entries:
        db.write_series(queue_path)
    yaml.dump(new_entries, sys.stdout)


def dequeue_videos(queue_path, paths):
    db = Db()
    db.load_series(queue_path)
    videos_set = set()
    alias_set = set()

    for path in paths:
        if _is_url(path) or _is_video(path):
            videos_set.add(path)
        elif os.path.isdir(path):
            if Db.path_has_series_db(path):
                alias_set.add(path)
            else:
                video = _find_candidate_in_directory(path)
                video_set.add(video)

    db.filter_db(
        lambda entry: entry['video'] not in videos_set and
            entry.get('alias', None) not in alias_set
    )
    db.write_series(queue_path)
