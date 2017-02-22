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
            with open(self.log_file_name) as data_fp:
                text = data_fp.read()
        except Exception:
            text = ""
        self.model = markovify.Text(text, state_size=self.state_size)
        self.data_fp = open(self.log_file_name, "a+")

    def make_sentence_with_start(self, start):
        return self.model.make_sentence_with_start(start)

    def make_sentence(self, tries=20):
        return self.model.make_sentence(tries=tries)


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
