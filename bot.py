import os
import asyncio
import sys
import logging
import logging.handlers
import traceback
import aiohttp
import config

import discord
from discord.ext import commands

script_name = os.path.basename(__file__).split('.')[0]

log_file_name = f"{script_name}.log"

# Limit of discord (non-nitro) is 8MB (not MiB)
max_file_size = 1000 * 1000 * 8
backup_count = 3
file_handler = logging.handlers.RotatingFileHandler(
	filename=log_file_name, maxBytes=max_file_size, backupCount=backup_count)
stdout_handler = logging.StreamHandler(sys.stdout)

log_format = logging.Formatter(
	'[%(asctime)s] {%(filename)s:%(lineno)d} %(levelname)s - %(message)s')
file_handler.setFormatter(log_format)
stdout_handler.setFormatter(log_format)

log = logging.getLogger('discord')
log.setLevel(logging.INFO)
log.addHandler(file_handler)
log.addHandler(stdout_handler)

def get_prefix(bot, message):
	prefixes = config.prefixes
	return commands.when_mentioned_or(*prefixes)(bot, message)

initial_extensions = [ ]

bot = commands.Bot(command_prefix=get_prefix,
				   description=config.bot_description, pm_help=True)

bot.log = log
# bot.loop = asyncio.get_event_loop()
bot.config = config
bot.script_name = script_name
bot.game_config = {
	'Pokemon Red': ('roms/Pokemon Red.gb',(0xf8e8f8,0x50a0f8,0x3050d0,0x101018)),
	'Pokemon Green': ('roms/Pokemon Green.gb',(0xf8e8f8,0x80d0a0,0x58a048,0x101018)),
	'Pokemon Blue': ('roms/Pokemon Blue.gb',(0xf8e8f8,0xd8a090,0xb87858,0x101018)),
	'Pokemon Yellow': ('roms/Pokemon Yellow.gb',(0xf8e8f8,0x70e0f8,0x00a0d0,0x101018)),
	'Pokemon Gold': ('roms/Pokemon Gold.gb',(0xf8f8f8,0x50b8a0,0x285858,0x181818)),
	'Pokemon Silver': ('roms/Pokemon Silver.gb',(0xf8e8f8,0xAAAAAA,0x777777,0x181010)),
}

if __name__ == '__main__':
	bot.load_extension('cogs.Poke6x')

@bot.event
async def on_ready():
	aioh = {"User-Agent": f"{script_name}/1.0'"}
	bot.aiosession = aiohttp.ClientSession(headers=aioh)
	bot.app_info = await bot.application_info()
	bot.botlog_channel = bot.get_channel(config.botlog_channel)

	log.info(f'\nLogged in as: {bot.user.name} - '
			 f'{bot.user.id}\ndpy version: {discord.__version__}\n')
	game_name = f"{config.prefixes[0]}help"

	guild = bot.botlog_channel.guild
	msg = f"{bot.user.name} has started! "\
		  f"{guild.name} has {guild.member_count} members!"

	activity = discord.Activity(name=game_name,
								type=discord.ActivityType.listening)
	await bot.change_presence(activity=activity)


@bot.event
async def on_command(ctx):
	log_text = f"{ctx.message.author} ({ctx.message.author.id}): "\
			   f"\"{ctx.message.content}\" "
	if ctx.guild:  # was too long for tertiary if
		log_text += f"on \"{ctx.channel.name}\" ({ctx.channel.id}) "\
					f"at \"{ctx.guild.name}\" ({ctx.guild.id})"
	else:
		log_text += f"on DMs ({ctx.channel.id})"
	log.info(log_text)


@bot.event
async def on_error(event_method, *args, **kwargs):
	log.error(f"Error on {event_method}: {sys.exc_info()}")


@bot.event
async def on_command_error(ctx, error):
	#Pass all unrecognized commands to the pyboy cog first
	if await bot.cogs['PyBoyCog'].handle_input(ctx):
		print("PyBoy Parser Successfully parsed input.")
		return True

	error_text = str(error)

	err_msg = f"Error with \"{ctx.message.content}\" from "\
			  f"\"{ctx.message.author} ({ctx.message.author.id}) "\
			  f"of type {type(error)}: {error_text}"

	log.error(err_msg)

	if not isinstance(error, commands.CommandNotFound):
		err_msg = bot.escape_message(err_msg)
		await bot.botlog_channel.send(err_msg)

	if isinstance(error, commands.NoPrivateMessage):
		return await ctx.send("This command doesn't work on DMs.")
	elif isinstance(error, commands.MissingPermissions):
		roles_needed = '\n- '.join(error.missing_perms)
		return await ctx.send(f"{ctx.author.mention}: You don't have the right"
							  " permissions to run this command. You need: "
							  f"```- {roles_needed}```")
	elif isinstance(error, commands.BotMissingPermissions):
		roles_needed = '\n-'.join(error.missing_perms)
		return await ctx.send(f"{ctx.author.mention}: Bot doesn't have "
							  "the right permissions to run this command. "
							  "Please add the following roles: "
							  f"```- {roles_needed}```")
	elif isinstance(error, commands.CommandOnCooldown):
		return await ctx.send(f"{ctx.author.mention}: You're being "
							  "ratelimited. Try in "
							  f"{error.retry_after:.1f} seconds.")
	elif isinstance(error, commands.CheckFailure):
		return await ctx.send(f"{ctx.author.mention}: Check failed. "
							  "You might not have the right permissions "
							  "to run this command, or you may not be able "
							  "to run this command in the current channel.")
	elif isinstance(error, commands.CommandInvokeError) and\
			("Cannot send messages to this user" in error_text):
		return await ctx.send(f"{ctx.author.mention}: I can't DM you.\n"
							  "You might have me blocked or have DMs "
							  f"blocked globally or for {ctx.guild.name}.\n"
							  "Please resolve that, then "
							  "run the command again.")
	elif isinstance(error, commands.CommandNotFound):
		# Nothing to do when command is not found.
		return

	help_text = f"Usage of this command is: ```{ctx.prefix}"\
				f"{ctx.command.signature}```\nPlease see `{ctx.prefix}help "\
				f"{ctx.command.name}` for more info about this command."
	if isinstance(error, commands.BadArgument):
		return await ctx.send(f"{ctx.author.mention}: You gave incorrect "
							  f"arguments. {help_text}")
	elif isinstance(error, commands.MissingRequiredArgument):
		return await ctx.send(f"{ctx.author.mention}: You gave incomplete "
							  f"arguments. {help_text}")

@bot.event
async def on_message(message):
	if message.author.bot:
		return

	if (message.guild) and (message.guild.id not in config.guild_whitelist):
		return

	ctx = await bot.get_context(message)
	await bot.invoke(ctx)

if not os.path.exists("data"): os.makedirs("data")
bot.run(config.token, bot=True, reconnect=True)