# babies

[![build status](https://circleci.com/gh/insidewhy/babies.png?style=shield)](https://circleci.com/gh/insidewhy/babies)

`babies` is a script for watching TV shows and movies and recording everything that has been watched in a giant log.
It can also keep track of your position within a series and/or within a video.

## Usage

Say a directory contains three videos in a series:

```bash
% ls /media/show
Episode 1.mp4
Episode 2.mp4
Episode 3.mp4
```

If you want to watch this series in order first create a `babies` db in the directory:
```bash
% babies create /media/show
```

This creates a file `/media/show/.videos.yaml` which you can edit if you want. To watch the next episode:
```bash
% babies watch /media/show
```

This will watch the show with `mpv` and when you are done it will update the file at `/media/show/.videos.yaml` to record your viewing session.

Most commands which accept a directory or filename will choose the current directory if the argument is not specified. There are also shorter aliases for every command. The following command is equivalent to the previous:
```bash
% cd /media/show
% babies w
```

If you exit the video early, then next time you try to watch the series it will resume from the point in the video where you exited. If you watch to the end of the video then the next invocation will play the next episode in the series.

All your watching sessions are also recorded in a giant log at `$HOME/.videorecord.yaml`, you can search through this record using the `find` command. Please see `babies --help` or `babies -h` for a full list of commands.

If watching at night it is useful to use normalised volume to avoid loud sections disturbing others, this can be done with:
```
% babies watch --night-mode /media/show
```

Or one of the following shortcuts:
```
% babies w -n /media/show
% babies n /media/show
```

If you watched the video elsewhere then you can record this fact in the log with a comment:
```
% babies record /media/show "Watched on another laptop"
```

The next time you try to watch the series it will start from the next video.

The following command can be used to play the video without recording it in any logs, this can be useful if you want to watch the first few seconds of a video to make sure `babies` will select the right video:
```
% babies dryrun /media/show
```
