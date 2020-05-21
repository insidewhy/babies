import sys
from readchar import readchar
from typing import Callable
import termios
from threading import Thread

KeyHandler = Callable[[str], None]


class ReadInput:
    def __init__(self):
        self.__started = False
        self.__cleanup = None
        self.__handler = None
        self.__keyqueue = []

    def start(self, handler: KeyHandler):
        self.__handler = handler

        for key in self.__keyqueue:
            handler(key)
        self.__keyqueue.clear()

        if not self.__started:
            self.__read_keypresses()

    def stop(self):
        self.__handler = None

    def destroy(self):
        self.__handler = None
        if self.__cleanup:
            self.__cleanup()

    def __handle_keypress(self, key: str):
        if self.__handler:
            self.__handler(key)
        else:
            self.__keyqueue = []

    def __read_keypresses(self):
        if sys.stdin.isatty():
            self.__read_keypresses_for_tty()
        else:
            self.__read_keypresses_for_non_tty()

    def __read_keypresses_for_tty(self):
        def readchars():
            while True:
                c = readchar()
                if c == "\x1b":
                    # handle some escape sequences, e.g. left/right, not perfect
                    key_name = None
                    c2 = readchar()
                    if c2 == "[":
                        c = readchar()
                        if c == "A":
                            key_name = "UP"
                        elif c == "B":
                            key_name = "DOWN"
                        elif c == "C":
                            key_name = "RIGHT"
                        elif c == "D":
                            key_name = "LEFT"

                    if key_name:
                        self.__handle_keypress(key_name)
                else:
                    self.__handle_keypress(c)

        is_win = sys.platform in ("win32", "cygwin")

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

        self.__cleanup = cleanup

    def __read_keypresses_for_non_tty(self):
        def readlines():
            while True:
                line = sys.stdin.readline().strip()
                for cmd in line.split():
                    self.__handle_keypress(cmd)

        cmd_thread = Thread(target=readlines)
        cmd_thread.daemon = True
        cmd_thread.start()
