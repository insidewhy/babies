#!/usr/bin/env python

import mpv
import sys

player = mpv.MPV(input_default_bindings=True, input_vo_keyboard=True)
player.fullscreen = True
player.vo = 'gpu'

@player.on_key_press('q')
def my_q_binding():
    print('TODO: save watching time etc.')
    player.quit()

player.play(sys.argv[1])
player.wait_for_playback()

