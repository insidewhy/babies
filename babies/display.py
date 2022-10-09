import sys
from typing import Optional, Tuple
from Xlib import display as xlib_display
from Xlib.ext import randr

from .config import Config, ConfigDisplays
from .yaml import yaml


def __get_display_name_width_and_height() -> Optional[Tuple[int, int, int]]:
    d = xlib_display.Display()
    s = d.screen()
    window = s.root.create_window(0, 0, 1, 1, 1, s.root_depth)
    res = randr.get_screen_resources(window)
    geometry = s.root.get_geometry()
    width = geometry.width
    height = geometry.height
    for output in res.outputs:
        params = d.xrandr_get_output_info(output, res.config_timestamp)
        if params.crtc:
            return params.name, width, height


def __get_current_display(
    displays: ConfigDisplays, display_info: Tuple[int, int, int]
) -> Optional[str]:
    display_name, width, height = display_info
    for name, display in displays.items():
        if display["output"] == display_name:
            s_width, s_height = display["mode"].split("x")
            if width == int(s_width) and height == int(s_height):
                return name


def __print_display(displays: ConfigDisplays, current: str, verbose: bool):
    if verbose:
        yaml.dump({"displays": list(displays.keys()), "current": current}, sys.stdout)
    else:
        print(current)


def get_display(config: Config, verbose=False):
    config.load()
    displays = config.get_displays()
    display_info = __get_display_name_width_and_height()
    if display_info is None:
        __print_display(displays, "unknown", verbose)
    else:
        display_name = __get_current_display(displays, display_info)
        if display_name is None:
            __print_display(displays, "unknown", verbose)
        else:
            __print_display(displays, display_name, verbose)
