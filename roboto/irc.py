import irc3
from roboto import parse_message, model


@irc3.plugin
class MarkovPlugin(object):

    def __init__(self, bot):
        self.bot = bot
        self.input_lines = 0
        try:
            self.ignored = bot.config.ignored_users
        except AttributeError:
            self.ignored = []
        self.last_cmd_time = 0

    @irc3.event(irc3.rfc.PRIVMSG)
    async def parse_input(self, mask, target, data, event):
        if mask.nick.lower() in self.ignored:
            return
        msg = await parse_message(data)
        if msg:
            self.bot.privmsg(target, msg)
        else:
            model.record(data)
            self.input_lines += 1
            if self.input_lines % 5 == 0:
                model.rebuild_chain()
            print(target, mask, data)
