# -*- coding: utf-8 -*-
"""

"""
from __future__ import unicode_literals, absolute_import

import string


def normalize(t):
    if t.startswith("!"):
        return False
    t = " ".join(t.strip().split(" "))
    if not t.endswith("."):
        t += "."
    if len(t) < 10:
        return False
    return t


def parse(input_file, output_file):
    with open(input_file) as input_fp:
        with open(output_file, "w+") as output_fp:
            for line in input_fp:
                p = "".join(filter(string.printable[:-5].__contains__, line)).split(">", 1)
                try:
                    text = normalize(p[1])
                    if not text:
                        continue
                    text_l = text.lower()
                    if "boreasbot" in text_l or "http" in text_l:
                        continue
                    if text.startswith("!"):
                        continue
                    if len(text) < 15:
                        continue
                    print(text)
                except IndexError:
                    pass
                else:
                    output_fp.write(text + "\n")

parse("/home/leigh/.config/hexchat/scrollback/twitch/#manofsnow.txt", "corpus.txt")
