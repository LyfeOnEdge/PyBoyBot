import io, os, time
import config
import discord
from discord.ext import commands
from discord.ext.commands import Cog
from PIL import Image, ImageDraw, ImageFont

import pyboy
COMMAND_SEP = ","

HELP_MESSAGE =	f"Start your command and separate each input with '{COMMAND_SEP}':\n"
HELP_MESSAGE +=  f"\t\tExample: `{COMMAND_SEP}u{COMMAND_SEP}r{COMMAND_SEP}a` *Move up, press right, press A*\n\n"
HELP_MESSAGE +=  "Use numbers to hold the button longer, A and B spam button presses instead of holding:\n"
HELP_MESSAGE += f"\t\tExample: `{COMMAND_SEP}u4{COMMAND_SEP}r3{COMMAND_SEP}a6` *Move up 4, right 3, spam A 6 times*\n\n"
HELP_MESSAGE += "**Commands:** (Command in parenthesis)\n"
HELP_MESSAGE += f"\t`(u)p | (d)own | (l)eft | (r)ight | (a) | (b) | (s)elect | (p)ause`"
MAX_WAIT = 600

FRAMES_PER_ACTION = 8
FRAMES_BETWEEN_ACTIONS = 8

GB_SCREEN_SIZE = (160,144)

class INPUT_ENUM:
	UP                  = 1
	DOWN                = 2
	LEFT                = 3
	RIGHT               = 4
	A                   = 5
	B                   = 6
	SELECT              = 7
	START               = 8

	string = {
		UP                  : "Pressed Up",
		DOWN                : "Pressed Down",
		LEFT                : "Pressed Left",
		RIGHT               : "Pressed Right",
		A                   : "Pressed A",
		B                   : "Pressed B",
		SELECT              : "Pressed Select",
		START               : "Pressed Start",
	}

	action_string = {
		pyboy.WindowEvent.PRESS_ARROW_UP        : "Pressed Up",
		pyboy.WindowEvent.PRESS_ARROW_DOWN      : "Pressed Down",
		pyboy.WindowEvent.PRESS_ARROW_LEFT      : "Pressed Left",
		pyboy.WindowEvent.PRESS_ARROW_RIGHT     : "Pressed Right",
		pyboy.WindowEvent.PRESS_BUTTON_A        : "Pressed A",
		pyboy.WindowEvent.PRESS_BUTTON_B        : "Pressed B",
		pyboy.WindowEvent.PRESS_BUTTON_SELECT   : "Pressed Select",
		pyboy.WindowEvent.PRESS_BUTTON_START    : "Pressed Start",
		pyboy.WindowEvent.RELEASE_ARROW_UP      : "Released Up",
		pyboy.WindowEvent.RELEASE_ARROW_DOWN    : "Released Down",
		pyboy.WindowEvent.RELEASE_ARROW_LEFT    : "Released Left",
		pyboy.WindowEvent.RELEASE_ARROW_RIGHT   : "Released Right",
		pyboy.WindowEvent.RELEASE_BUTTON_A      : "Released A",
		pyboy.WindowEvent.RELEASE_BUTTON_B      : "Released B",
		pyboy.WindowEvent.RELEASE_BUTTON_SELECT : "Released Select",
		pyboy.WindowEvent.RELEASE_BUTTON_START  : "Released Start",
	}

	COMMAND_MAP = {
		"u"             :   UP,
		"d"             :   DOWN,
		"l"             :   LEFT,
		"r"             :   RIGHT,
		"a"             :   A,
		"b"             :   B,
		"s"             :   SELECT,
		"p"             :   START,
	}

	ACTIONS = {
		UP      :   (pyboy.WindowEvent.PRESS_ARROW_UP,pyboy.WindowEvent.RELEASE_ARROW_UP),
		DOWN    :   (pyboy.WindowEvent.PRESS_ARROW_DOWN,pyboy.WindowEvent.RELEASE_ARROW_DOWN),
		LEFT    :   (pyboy.WindowEvent.PRESS_ARROW_LEFT,pyboy.WindowEvent.RELEASE_ARROW_LEFT),
		RIGHT   :   (pyboy.WindowEvent.PRESS_ARROW_RIGHT,pyboy.WindowEvent.RELEASE_ARROW_RIGHT),
		A       :   (pyboy.WindowEvent.PRESS_BUTTON_A,pyboy.WindowEvent.RELEASE_BUTTON_A),
		B       :   (pyboy.WindowEvent.PRESS_BUTTON_B,pyboy.WindowEvent.RELEASE_BUTTON_B),
		SELECT  :   (pyboy.WindowEvent.PRESS_BUTTON_SELECT,pyboy.WindowEvent.RELEASE_BUTTON_SELECT),
		START   :   (pyboy.WindowEvent.PRESS_BUTTON_START,pyboy.WindowEvent.RELEASE_BUTTON_START),
	}
	def __init__(self):
		pass

def handle_input(command):
	command = command.strip()
	parsed_command = parse_command(command)
	if parsed_command == -1:
		return parsed_command
	return generate_input_timeline_from_parsed_commands(parsed_command)

def parse_command(command):
	try:
		command=command[1:].lower()
		print(f"Parsing command {command}")
		if COMMAND_SEP in command:
			command = command.split(COMMAND_SEP)
		else:
			command = [command]
		parsed = []
		for c in command:
			c = c.strip()
			if len(c) > 1:
				c, count = c[0],c[1:]
				parsed.append((c,count))
			else:
				parsed.append(c)
		return parsed
	except Exception as e:
		print(f"Error parsing command {command} - {e}")
		return -1

def generate_input_timeline_from_parsed_commands(inputs):
	timeline = []
	for i in inputs:
		if type(i) is str:
			if i in ('', ' '): continue
			if not INPUT_ENUM.COMMAND_MAP.get(i):
				return -1
			timeline.append(INPUT_ENUM.ACTIONS[INPUT_ENUM.COMMAND_MAP[i]][0])
			for _ in range(int(FRAMES_PER_ACTION)): timeline.append([]) #Empty frames for wait
			timeline.append(INPUT_ENUM.ACTIONS[INPUT_ENUM.COMMAND_MAP[i]][1]) #Unpress button
			for _ in range(FRAMES_PER_ACTION): timeline.append([])
		else:
			inp, count = i
			if not INPUT_ENUM.COMMAND_MAP.get(inp):
				return -1
			try:
				count = int(count)
				if count > 10: count = 10
				if count < 1: count = 1
				count *= 2
			except:
				return -1

			if INPUT_ENUM.COMMAND_MAP.get(inp) in [INPUT_ENUM.A, INPUT_ENUM.B]:
				for i in range(count):
					timeline.append(INPUT_ENUM.ACTIONS[INPUT_ENUM.COMMAND_MAP[inp]][0])
					for _ in range(FRAMES_PER_ACTION): timeline.append([]) #Empty frames for wait
					timeline.append(INPUT_ENUM.ACTIONS[INPUT_ENUM.COMMAND_MAP[inp]][1]) #Unpress button
					for _ in range(FRAMES_PER_ACTION*2): timeline.append([])
			else:
				timeline.append(INPUT_ENUM.ACTIONS[INPUT_ENUM.COMMAND_MAP[inp]][0])
				for _ in range(FRAMES_PER_ACTION*count): timeline.append([]) #Empty frames for wait
				timeline.append(INPUT_ENUM.ACTIONS[INPUT_ENUM.COMMAND_MAP[inp]][1]) #Unpress button
				for _ in range(FRAMES_PER_ACTION): timeline.append([])
	return timeline

class GameBoy:
	def __init__(self, name, file, color_palette):
		self.title = name
		self.file = file
		self.color_palette = color_palette
		self.game = pyboy.PyBoy(file,window_type="headless",color_palette=color_palette)
		self.screen = self.game.botsupport_manager().screen()

	def update(self):
		self.game.tick()
		self.game.screen_image().convert("RGBA").tobytes()

	def handle_input(self):
		pass

	def reinitialize(self):
		del self.game
		del self.screen
		self.game = pyboy.PyBoy(self.file,window_type="headless",color_palette=self.color_palette)
		self.screen = self.game.botsupport_manager().screen()

	def load_state(self):
		if os.path.isfile("./"+self.file+".state"):
			self.game.send_input(pyboy.WindowEvent.STATE_LOAD)
			self.game.tick()
		else:
			print(f"Skipping load_state for {self.file}, no save state found")

	def save_state(self):
		self.game.send_input(pyboy.WindowEvent.STATE_SAVE)
		self.game.tick()
		self.game.tick()
		self.game.tick()
		self.game.tick()

PAD = 10
TITLE_HEIGHT = 12
TEXT_HEIGHT = TITLE_HEIGHT + 1

class PyBoyCog(Cog):
	def __init__(self, bot):
		self.bot = bot
		self.game_config = bot.game_config
		self.games = {}

		for name in self.game_config.keys():
			conf = self.game_config[name]
			gb = GameBoy(name, conf[0], conf[1])
			gb.load_state()
			self.games[name]=gb

	def save_games(self):
		for g in self.games.keys(): self.games[g].save_state()

	def load_games(self):
		for g in self.games.keys(): self.games[g].load_state()
 
	def render(self):
		base_image = Image.new("RGB", ((160+PAD)*3+PAD,(144+PAD)*2+PAD+2*TITLE_HEIGHT), (0,0,0,255))
		fnt = ImageFont.truetype("JetBrainsMono-Bold.ttf", TEXT_HEIGHT)
		draw = ImageDraw.Draw(base_image)
		i = 0
		for g in self.games:
			if i > 2:
				image = self.games[g].game.screen_image().convert("RGB")
				base_image.paste(image, (PAD+(i-3)*(160+PAD),144+2*PAD+2*TITLE_HEIGHT))
				w, h = draw.textsize(self.games[g].title, font=fnt)
				draw.text((PAD+(i-3+0.5)*(160+PAD)-w/2,144+2*PAD+TITLE_HEIGHT-2), self.games[g].title, font=fnt, fill=(255, 255, 255, 255))
			else:
				image = self.games[g].game.screen_image().convert("RGB")
				base_image.paste(image, (PAD+i*(160+PAD),0+PAD+TITLE_HEIGHT))
				w, h = draw.textsize(self.games[g].title, font=fnt)
				draw.text((PAD+(i+0.5)*(160+PAD)-w/2,0+PAD-2), self.games[g].title, font=fnt, fill=(255, 255, 255, 255))
			i += 1
		w,h = base_image.size
		base_image.resize((w*2,h*2), Image.NONE)
		base_image.save("data/temp.png")
		return discord.File("data/temp.png")

	async def handle_input(self, ctx):
		print(f"Handling {ctx.message.content}")
		handled = handle_input(ctx.message.content)
		if handled == -1: return False
		for a in handled:
			for g in self.games.keys():
				if a: self.games[g].game.send_input(a)
				self.games[g].game.tick()
		for g in self.games.keys():
			for i in range(300):
				self.games[g].game.tick()
		self.save_games()

		await ctx.channel.send(file=self.render())
		return True

	@commands.command()
	async def inputs(self, ctx):
		"""Details the PyBoyBot input system"""
		await ctx.send(HELP_MESSAGE)

	# @commands.command()
	# async def save(self, ctx):
	# 	"""Forces the games to save their state"""
	# 	self.save_games()
	# 	await ctx.channel.send(file=self.render())

	# @commands.command()
	# async def load(self, ctx):
	# 	"""Forces the games to load their last save state"""
	# 	self.load_games()
	# 	await ctx.channel.send(file=self.render())

	@commands.command()
	async def wait(self, ctx, count=None):
		"""Waits a given number of frame in game."""
		if count:
			count = int(count)
			count = min(count, MAX_WAIT)
			for g in self.games.keys():
				for i in range(count):
					self.games[g].game.tick()
			self.save_games()
			await ctx.channel.send(file=self.render())
		else: 
			await ctx.channel.send(f"{ctx.author.mention}, you must specify a number of frames to wait (60 frames per second) max {MAX_WAIT}.")
		
	@commands.guild_only()
	@commands.command()
	async def membercount(self, ctx):
		"""Prints the member count of the server."""
		await ctx.send(f"{ctx.guild.name} has "
					   f"{ctx.guild.member_count} members!")

	@commands.command(aliases=["pyboy", "pyboybot"])
	async def about(self, ctx):
		"""Shows a quick embed with bot info."""
		embed = discord.Embed(title="PyBoyBot",
							  url=config.source_url,
							  description=config.embed_desc)

		embed.set_thumbnail(url=self.bot.user.avatar_url)

		await ctx.send(embed=embed)

	@commands.command()
	async def ping(self, ctx):
		"""Shows ping values to discord.

		RTT = Round-trip time, time taken to send a message to discord
		GW = Gateway Ping"""
		before = time.monotonic()
		tmp = await ctx.send('Calculating ping...')
		after = time.monotonic()
		rtt_ms = (after - before) * 1000
		gw_ms = self.bot.latency * 1000

		message_text = f":ping_pong:\n"\
					   f"rtt: `{rtt_ms:.1f}ms`\n"\
					   f"gw: `{gw_ms:.1f}ms`"
		self.bot.log.info(message_text)
		await tmp.edit(content=message_text)

def setup(bot):
	bot.add_cog(PyBoyCog(bot))