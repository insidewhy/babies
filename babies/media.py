import sys
import os
import re
import ffmpeg
from typing import List, Union, Tuple, Optional
from datetime import datetime

from .formatting import format_duration, format_time_with_duration
from .videos import watch_video
from .spotify import listen_to_track
from .input import ReadInput
from .db import Db
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
]


def _is_url(path: str) -> bool:
    return path.startswith("https://") or path.startswith("http://")


def _get_media_entry_for_log(video_path: str) -> str:
    return video_path if _is_url(video_path) else os.path.basename(video_path)


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
) -> Tuple[str, Optional[dict]]:
    """
        If path is a directory then load series into db and return next
        unwatched show else return path to file
    """
    if _is_url(path):
        return path, None
    elif os.path.isdir(path):
        if db.load_series(path):
            video_entry = db.get_next_in_series()
            if not video_entry:
                raise ValueError("series is complete")

            video = video_entry["video"]
            alias = video_entry.get("alias", None)
            if _is_url(video):
                video_path = video
            elif alias:
                video_path = os.path.join(path, alias, video)
            else:
                video_path = os.path.join(path, video)

            return video_path, video_entry
        else:
            return _find_candidate_in_directory(path), None

    elif os.path.isfile(path):
        return path, None
    else:
        raise ValueError(f"No video found at {path}")


def record_media(path, comment):
    db = Db()
    video_path, video_entry = _path_to_media(db, path)
    duration = format_duration(float(ffmpeg.probe(video_path)["format"]["duration"]))

    video_filename = _get_media_entry_for_log(video_path)
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

    if video_entry:
        video_entry["duration"] = duration
        viewings = video_entry.setdefault("viewings", [])
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
    if uri.startswith("spotify:"):
        listen_to_track(read_input, uri)
    else:
        db = Db()
        video_path, video_entry = _path_to_media(db, uri)
        video_for_log = _get_media_entry_for_log(video_path)

        start_time = datetime.now()

        start_position = 0
        viewings = video_entry and video_entry.get("viewings", None)
        if viewings:
            final_viewing = viewings[-1]["end"].split(" at ")[1]
            start_position = _parse_duration(final_viewing)

        position, formatted_duration, end_time = watch_video(
            read_input,
            uri,
            video_path,
            video_for_log,
            start_position,
            night_mode=night_mode,
            sub_file=sub_file,
        )

        if not dont_record:
            start = format_time_with_duration(start_time, start_position)
            end = format_time_with_duration(end_time, position)

            record = {
                "video": video_for_log,
                "duration": formatted_duration,
                "start": start,
                "end": end,
            }
            if comment:
                record["comment"] = comment
            elif video_entry and "comment" in video_entry:
                record["comment"] = video_entry["comment"]

            if title:
                record["title"] = title
            elif video_entry and "title" in video_entry:
                record["title"] = video_entry["title"]

            # append the global record first in case the series update fails due to full
            # disk or readonly mount etc.
            db.append_global_record(record)
            print("recorded video in global record:", video_for_log)

            if video_entry:
                # reload database in case something was enqueued while the video
                # was being watched
                db.load_series(uri)
                video_entry_backup = video_entry
                video_entry = db.get_next_in_series()
                if (
                    not video_entry
                    or video_entry["video"] != video_entry_backup["video"]
                ):
                    print(
                        "Something changed while watching video, "
                        "not recording entry in series record",
                        file=sys.stderr,
                    )
                    return

                if video_entry.get("duration", None) != formatted_duration:
                    video_entry["duration"] = formatted_duration
                if comment:
                    video_entry["comment"] = comment
                if title:
                    video_entry["title"] = title
                viewings = video_entry.setdefault("viewings", [])

                viewings.append({"start": start, "end": end})
                db.write_series(uri)
                print("recorded video in series record:", video_for_log)

                if db.aliased_db:
                    # TODO: reload aliased_db in case it has changed?
                    next_aliased_entry = db.aliased_db.get_next_in_series()
                    if next_aliased_entry["video"] == video_entry["video"]:
                        next_aliased_entry["duration"] = formatted_duration
                        aliased_viewings = next_aliased_entry.setdefault("viewings", [])
                        aliased_viewings.append({"start": start, "end": end})
                        aliased_path = video_entry["alias"]
                        db.aliased_db.write_series(aliased_path)
                        print("recorded video in aliased series record:", aliased_path)


def print_path_to_media(
    paths: List[str], ignore_errors=False, verbose=False, no_extension_filter=False
):
    db = Db()
    logs: List[Union[str, dict]] = []

    for path in paths:
        try:
            video_path, _ = _path_to_media(
                db, path, ignore_errors=ignore_errors, verbose=verbose
            )
            if not no_extension_filter and not _is_video(video_path):
                continue

            filename = os.path.basename(video_path)
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
    queued_videos = db.get_series_video_set()

    if prune:
        db.prune_watched()

    entry_template = {}
    if comment:
        entry_template["comment"] = comment
    if title:
        entry_template["title"] = title

    def add_new_entry(video, alias=None):
        # don't allow duplicates
        if video not in queued_videos:
            entry = entry_template.copy()
            entry["video"] = video
            if alias:
                entry["alias"] = alias
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
                if next_entry and "alias" not in next_entry:
                    add_new_entry(next_entry["video"], path)
            else:
                video = _find_candidate_in_directory(path)
                add_new_entry(video)

    if new_entries:
        db.write_series(queue_path)
    yaml.dump(new_entries, sys.stdout)


def dequeue_media(queue_path, paths):
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
                videos_set.add(video)

    db.filter_db(
        lambda entry: entry["video"] not in videos_set
        and entry.get("alias", None) not in alias_set
    )
    db.write_series(queue_path)


def grep_media_record(terms, quiet):
    db = Db()
    db.load_global_record()
    matches = db.get_matching_entries(
        lambda record: all(
            re.search(term, record["video"], re.IGNORECASE) for term in terms
        )
    )

    if quiet:
        print("\n".join(list(map(lambda m: m["video"], matches))))
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
