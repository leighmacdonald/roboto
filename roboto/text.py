import string

import markovify

from roboto import config


class MarkovModel(object):
    def __init__(self, log_file_name, state_size=2):
        self.data_fp = None
        self.log_file_name = log_file_name
        self.state_size = state_size
        self.model = None
        self.rebuild_chain()

    def rebuild_chain(self):
        if self.data_fp is not None:
            self.data_fp.close()
        try:
            with open(self.log_file_name, encoding="utf8") as data_fp:
                text = data_fp.read()
        except Exception:
            text = ""
        self.model = markovify.Text(text, state_size=self.state_size)
        self.data_fp = open(self.log_file_name, "a+")

    def make_sentence_with_start(self, start):
        return self.model.make_sentence_with_start(start)

    def make_sentence(self, tries=20):
        return self.model.make_sentence(tries=tries)

    def record(self, sentence):
        norm_str = normalize(sentence)
        if norm_str:
            self.data_fp.write(norm_str + "\n")
            self.data_fp.flush()


def normalize(t):
    if t.startswith("!"):
        return False
    if "http" in t.lower():
        return False
    t = " ".join(t.strip().split(" "))
    if not t.endswith("."):
        t += "."
    if len(t) < 10:
        return False
    return t


def add_cmd_prefix(cmd):
    return "{}{}".format(config.get("cmd", "!"), cmd)


def parse_xchat_log(input_file, output_file):
    ignores = ["http"]
    ignores.extend(config.ignored_users)
    with open(input_file) as input_fp:
        with open(output_file, "w+") as output_fp:
            for line in input_fp:
                p = "".join(filter(string.printable[:-5].__contains__, line)).split(">", 1)
                try:
                    text = normalize(p[1])
                    if not text:
                        continue
                    text_l = text.lower()
                    skipped = False
                    for ignore_txt in ignores:
                        if ignore_txt in text_l:
                            skipped = True
                            break
                    if skipped:
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
