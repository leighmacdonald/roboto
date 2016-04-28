# -*- coding: utf-8 -*-
import markovify
import irc3
from os.path import dirname, join, abspath

import time

default_file_name = abspath(join(dirname(__file__), "corpus.txt"))


@irc3.plugin
class MarkovPlugin(object):

    def __init__(self, bot, log_file_name=default_file_name, state_size=2):
        self.log_file_name = log_file_name
        self.bot = bot
        self.data_fp = None
        self.model = None
        self.input_lines = 0
        self.ignored = ["boreasbot"]
        self.state_size = state_size

        self.rebuild_chain()

    def rebuild_chain(self):
        print("Rebuilding chain...")
        if self.data_fp is not None:
            self.data_fp.close()
        try:
            with open(self.log_file_name) as data_fp:
                text = data_fp.read()
        except FileNotFoundError:
            text = ""
        self.model = markovify.Text(text, state_size=self.state_size)
        self.data_fp = open(self.log_file_name, "a+")

    def normalize(self, t):
        if t.startswith("!"):
            return False
        if "http" in t.lower():
            return False
        t = " ".join(t.strip().split(" "))
        if not t.endswith("."):
            t += "."
        if len(t) < 10:
            return False
        self.input_lines += 1
        if self.input_lines % 5 == 0:
            self.rebuild_chain()
        return t

    def record(self, sentence):
        norm_str = self.normalize(sentence)
        if norm_str:
            self.data_fp.write(norm_str + "\n")
            self.data_fp.flush()

    @irc3.event(irc3.rfc.PRIVMSG)
    def parse_input(self, mask, target, data, event):
        if mask.nick.lower() in self.ignored:
            return
        if data.startswith("~talk"):
            t = self.model.make_sentence(tries=20)
            time.sleep(2)
            self.bot.privmsg(target, "> " + t)
        else:
            self.record(data)
            print(target, mask, data)
