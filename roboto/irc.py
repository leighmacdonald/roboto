import irc3
from roboto import commands, markov_model


@irc3.plugin
class TwitchClient(object):

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
        task = commands.parse_message(data)
        if task:
            task.set_client_twitch(self.bot)
            task.set_source(commands.TaskSource.twitch)
            task.set_channel(target)
            task.set_user(mask.nick)
            await commands.dispatcher.add_task(task)
        else:
            markov_model.record(data)
            self.input_lines += 1
            if self.input_lines % 1 == 0:
                await commands.dispatcher.add_task(
                    commands.TaskState(commands.Commands.rebuild_markov, []))
                markov_model.rebuild_chain()
