import sys
import os
import re
from typing import List, Union, Tuple, Optional
from datetime import datetime
from subprocess import check_output

from .formatting import format_duration, format_time_with_duration
from .videos import watch_video
from .spotify import listen_to_track
from .input import ReadInput
from .db import Db, MediaEntry
from .yaml import yaml

SHOW_EXTENSIONS = [
    "mkv",
    "avi",
    "mpg",
    "mp4",
    "mpeg",
    "ogv",
    "wmv",
    "flv",
    "m4v",
    "iso",
    "mov",
    "webm",
]


def _is_url(path: str) -> bool:
    return path.startswith("https://") or path.startswith("http://")


def _is_spotify(path: str) -> bool:
    return path.startswith("spotify:")


def _get_media_path(media_entry: MediaEntry) -> str:
    video = media_entry.get("video", None)
    try:
        return video or media_entry["audio"]
    except:
        print("bad entry", media_entry)
        raise


def _get_media_entry_for_log(media_path: str) -> str:
    return media_path if _is_url(media_path) else os.path.basename(media_path)


def _is_video(path):
    for suffix in SHOW_EXTENSIONS:
        if path.endswith("." + suffix):
            return True
    return False


def _find_candidate_in_directory(path: str) -> str:
    # if there is a single video in the directory then use it
    candidates = list(filter(_is_video, os.listdir(path)))
    candidate_count = len(candidates)
    if candidate_count == 0:
        raise ValueError(f"No videos found in directory {path}")
    elif candidate_count == 1:
        return os.path.join(path, candidates[0])
    else:
        # TODO: allow user to select with pager?
        raise ValueError("multiple candidates: " + ", ".join(candidates))


def _path_to_media(
    db: Db, path: str, ignore_errors=False, verbose=False
) -> Tuple[str, Optional[MediaEntry]]:
    """
    If path is a directory then load series into db and return next
    unwatched show else return path to file
    """
    if _is_url(path) or _is_spotify(path):
        return path, None
    elif os.path.isdir(path):
        if db.load_series(path):
            media_entry = db.get_next_in_series()
            if not media_entry:
                raise ValueError("series is complete")

            audio = media_entry.get("audio", None)
            if audio:
                media_path = audio
            else:
                video = media_entry["video"]
                alias = media_entry.get("alias", None)
                if _is_url(video):
                    media_path = video
                elif alias:
                    media_path = os.path.join(path, alias, video)
                else:
                    media_path = os.path.join(path, video)

            return media_path, media_entry
        else:
            return _find_candidate_in_directory(path), None

    elif os.path.isfile(path):
        return path, None
    else:
        raise ValueError(f"No video found at {path}")


def record_media(path, comment):
    db = Db()
    media_path, media_entry = _path_to_media(db, path)

    duration = format_duration(
        float(
            check_output(
                [
                    "ffprobe",
                    "-v",
                    "error",
                    "-show_entries",
                    "format=duration",
                    "-of",
                    "default=noprint_wrappers=1:nokey=1",
                    media_path,
                ]
            )
        )
    )

    video_filename = _get_media_entry_for_log(media_path)
    start = "unknown at " + format_duration(0)
    end = "unknown at " + duration
    db.append_global_record(
        {
            "video": video_filename,
            "duration": duration,
            "start": start,
            "end": end,
            "comment": comment,
        }
    )
    print("recorded " + video_filename + " in global log with comment: " + comment)

    if media_entry:
        media_entry["duration"] = duration
        viewings = media_entry.setdefault("viewings", [])
        viewings.append({"start": start, "end": end, "comment": comment})
        db.write_series(path)
        print("recorded " + video_filename + " in series log with comment: " + comment)


def _parse_duration(duration):
    hours, mins, secs = duration.split(":")
    return float(hours) * 3600 + float(mins) * 60 + float(secs)


def play_media(
    read_input: ReadInput,
    uri: str,
    dont_record=False,
    night_mode=False,
    sub_file=None,
    comment=None,
    title=None,
):
    if _is_spotify(uri):
        listen_to_track(read_input, uri)
    else:
        db = Db()
        media_path, media_entry = _path_to_media(db, uri)
        media_log_entry = _get_media_entry_for_log(media_path)

        start_time = datetime.now()
        start_position = 0

        if _is_spotify(media_path):
            position, formatted_duration, end_time = listen_to_track(
                read_input, media_path
            )

            if not dont_record:
                _record_session(
                    db,
                    media_entry,
                    uri,
                    media_log_entry,
                    start_time,
                    start_position,
                    end_time,
                    position,
                    formatted_duration,
                    comment=comment,
                    title=title,
                    is_audio=True,
                    skip_global_record=True,
                )
        else:
            if media_entry:
                viewings = media_entry.get("viewings", None)
                if viewings:
                    final_viewing = viewings[-1]["end"].split(" at ")[1]
                    start_position = _parse_duration(final_viewing)

            watch_status = watch_video(
                read_input,
                uri,
                media_path,
                media_log_entry,
                start_position,
                night_mode=night_mode,
                sub_file=sub_file,
            )

            if watch_status and not dont_record:
                position, formatted_duration, end_time = watch_status

                _record_session(
                    db,
                    media_entry,
                    uri,
                    media_log_entry,
                    start_time,
                    start_position,
                    end_time,
                    position,
                    formatted_duration,
                    comment=comment,
                    title=title,
                )


def _record_session(
    db: Db,
    media_entry: Optional[MediaEntry],
    uri: str,
    media_log_entry: str,
    start_time: datetime,
    start_position: int,
    end_time: datetime,
    position: int,
    formatted_duration: str,
    comment=None,
    title=None,
    is_audio=False,
    skip_global_record=False,
):
    start = format_time_with_duration(start_time, start_position)
    end = format_time_with_duration(end_time, position)

    record: MediaEntry = {}

    if is_audio:
        record["audio"] = media_log_entry
    else:
        record["video"] = media_log_entry

    record.update({"duration": formatted_duration, "start": start, "end": end})

    if comment:
        record["comment"] = comment
    elif media_entry and "comment" in media_entry:
        record["comment"] = media_entry["comment"]

    if title:
        record["title"] = title
    elif media_entry and "title" in media_entry:
        record["title"] = media_entry["title"]

    if not skip_global_record:
        # append the global record first in case the series update fails due to full
        # disk or readonly mount etc.
        db.append_global_record(record)
        print("recorded media in global record:", media_log_entry)

    if media_entry:
        # reload database in case something was enqueued while the media
        # was playing
        db.load_series(uri)
        media_entry_backup = media_entry
        media_entry = db.get_next_in_series()
        if not media_entry or _get_media_path(media_entry) != _get_media_path(
            media_entry_backup
        ):
            print(
                "Something changed while playing media, "
                "not recording entry in series record",
                file=sys.stderr,
            )
            return

        if media_entry.get("duration", None) != formatted_duration:
            media_entry["duration"] = formatted_duration
        if comment:
            media_entry["comment"] = comment
        if title:
            media_entry["title"] = title
        sessions = media_entry.setdefault("viewings", [])

        sessions.append({"start": start, "end": end})
        db.write_series(uri)
        print("recorded media in series record:", media_log_entry)

        if db.aliased_db:
            # TODO: reload aliased_db in case it has changed?
            next_aliased_entry = db.aliased_db.get_next_in_series()

            media_key = "audio" if is_audio else "video"
            if next_aliased_entry[media_key] == media_entry[media_key]:  # type: ignore
                next_aliased_entry["duration"] = formatted_duration
                aliased_sessions = next_aliased_entry.setdefault("viewings", [])
                aliased_sessions.append({"start": start, "end": end})
                aliased_path = media_entry["alias"]
                db.aliased_db.write_series(aliased_path)
                print("recorded video in aliased series record:", aliased_path)


def print_path_to_media(
    paths: List[str], ignore_errors=False, verbose=False, no_extension_filter=False
):
    db = Db()
    logs: List[Union[str, dict]] = []

    for path in paths:
        try:
            media_path, _ = _path_to_media(
                db, path, ignore_errors=ignore_errors, verbose=verbose
            )

            if _is_spotify(media_path):
                if verbose:
                    logs.append({"audio": media_path})
                else:
                    logs.append(media_path)
            else:
                if not no_extension_filter and not _is_video(media_path):
                    continue

                filename = os.path.basename(media_path)
                if verbose:
                    logs.append({"path": path, "filename": filename})
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


def enqueue_media(queue_path, paths, comment=None, prune=False, title=None):
    db = Db()
    db.load_series(queue_path)
    new_entries = []
    queue_media = db.get_series_media_set()

    if prune:
        db.prune_watched()

    entry_template = {}
    if comment:
        entry_template["comment"] = comment
    if title:
        entry_template["title"] = title

    def add_new_entry(media, alias=None, audio=False):
        # don't allow duplicates
        if media not in queue_media:
            entry = entry_template.copy()
            if audio:
                entry["audio"] = media
            else:
                entry["video"] = media
            if alias:
                entry["alias"] = alias
            new_entries.append(entry)
            queue_media.add(media)
            db.add_show_to_series(entry)

    for path in paths:
        if _is_url(path) or _is_video(path):
            add_new_entry(path)
        elif _is_spotify(path):
            add_new_entry(path, audio=True)
        elif os.path.isdir(path):
            series_db = Db()
            if series_db.load_series(path):
                # TODO: skip entries that are already enqueued, e.g.
                # first queue episode 1, then episode 2
                next_entry = series_db.get_next_in_series()
                if next_entry and "alias" not in next_entry:
                    add_new_entry(_get_media_path(next_entry), path)
            else:
                video = _find_candidate_in_directory(path)
                add_new_entry(video)

    if new_entries:
        db.write_series(queue_path)
    yaml.dump(new_entries, sys.stdout)


def dequeue_media(queue_path, paths):
    db = Db()
    db.load_series(queue_path)
    media_set = set()
    alias_set = set()

    for path in paths:
        if _is_url(path) or _is_video(path) or _is_spotify(path):
            media_set.add(path)
        elif os.path.isdir(path):
            if Db.path_has_series_db(path):
                alias_set.add(path)
            else:
                video = _find_candidate_in_directory(path)
                media_set.add(video)

    db.filter_db(
        lambda entry: _get_media_path(entry) not in media_set
        and entry.get("alias", None) not in alias_set
    )
    db.write_series(queue_path)


def grep_media_record(terms, quiet):
    db = Db()
    db.load_global_record()
    matches = db.get_matching_entries(
        lambda record: all(
            re.search(term, _get_media_path(record), re.IGNORECASE) for term in terms
        )
    )

    if quiet:
        print("\n".join(list(map(_get_media_path, matches))))
    else:
        yaml.dump(list(matches), sys.stdout)


def create_record_from_directory(db: Db, dirpath, force):
    # TODO: merge new content with old content instead
    if not force and os.path.isfile(Db.get_series_db_path(dirpath)):
        raise ValueError("series record already exists")

    for filename in sorted(os.listdir(dirpath)):
        if _is_video(filename):
            db.add_show_to_series({"video": filename})

    db.write_series(dirpath)
