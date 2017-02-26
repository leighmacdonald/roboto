import string
from logging import getLogger
from urllib.parse import urlparse
import markovify
from sqlalchemy import orm
from roboto import config


valid_url_schemas = ("http", "https")

log = getLogger()


def valid_url(url: str, allowed_domains=None) -> bool:
    u = urlparse(url, allow_fragments=False)
    if allowed_domains and u.netloc not in allowed_domains:
        return False
    return u.scheme in valid_url_schemas and u.netloc


class MarkovModel(object):
    def __init__(self, server_id, state_size=2):
        self.state_size = state_size
        self.model = None
        self.server_id = server_id
        self._new_data = []

    def rebuild_chain(self, session: orm.Session):
        from roboto.model import UserMessage
        msgs = UserMessage.get_server_msgs(session, self.server_id)
        self.model = markovify.Text("".join([m.content for m in msgs]), state_size=self.state_size)
        log.debug("Read {} server messages".format(len(msgs)))

    def make_sentence_with_start(self, start):
        return self.model.make_sentence_with_start(start)

    def make_sentence(self, tries=20):
        return self.model.make_sentence(tries=tries)

    def record(self, sentence):
        s = normalize(sentence)
        if s:
            self._new_data.append("{}\n".format(s))


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
