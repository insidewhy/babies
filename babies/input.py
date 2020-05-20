import sys
from readchar import readchar
from typing import Callable
import termios
from threading import Thread

KeyHandler = Callable[[str], None]

def read_keypresses(handler: KeyHandler):
    if sys.stdin.isatty():
        return _read_keypresses_for_tty(handler)
    else:
        _read_keypresses_for_non_tty(handler)
        return None


def _read_keypresses_for_tty(handler: KeyHandler):
    def readchars():
        while True:
            c = readchar()
            if c == '\x1b':
                # handle some escape sequences, e.g. left/right, not perfect
                key_name = None
                c2 = readchar()
                if c2 == '[':
                    c = readchar()
                    if c == 'A':
                        key_name = 'UP'
                    elif c == 'B':
                        key_name = 'DOWN'
                    elif c == 'C':
                        key_name = 'RIGHT'
                    elif c == 'D':
                        key_name = 'LEFT'

                if key_name:
                    handler(key_name)
            else:
                handler(c)

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


def _read_keypresses_for_non_tty(handler: KeyHandler):
    def readlines():
        while True:
            line = sys.stdin.readline().strip()
            for cmd in line.split():
                handler(cmd)

    cmd_thread = Thread(target=readlines)
    cmd_thread.daemon = True
    cmd_thread.start()
