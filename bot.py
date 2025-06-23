import discord
from discord.ext import commands, tasks
import random
import string
import aiohttp
import yaml
import asyncio

# Wczytanie konfiguracji z pliku YAML
with open("config.yml", "r", encoding="utf-8") as f:
    config = yaml.safe_load(f)

TOKEN = config["token"]
GUILD_ID = config["guild_id"]
VERIFIED_ROLE_ID = config["verified_role_id"]
CHANNEL_ID = config["channel_id"]
BOT_ID = config["bot_id"]
VERIFICATION_URL = config["verification_url"]
THUMBNAIL = config["thumbnail"]

intents = discord.Intents.default()
intents.messages = True
intents.guilds = True
intents.members = True
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)
verification_map = {}  # user_id: code_id

# Mapowanie nazw stylów na Discord ButtonStyle
STYLE_MAP = {
    "primary": discord.ButtonStyle.primary,
    "secondary": discord.ButtonStyle.secondary,
    "success": discord.ButtonStyle.success,
    "danger": discord.ButtonStyle.danger
}

def generate_id(length=8):
    return ''.join(random.choices(string.ascii_letters + string.digits, k=length))

async def get_code_from_backend(code_id):
    async with aiohttp.ClientSession() as session:
        async with session.get(f"http://localhost:5000/api/code?id={code_id}") as resp:
            if resp.status == 200:
                data = await resp.json()
                return data.get("code")
            return None

@bot.event
async def on_ready():
    print(f"Zalogowano jako {bot.user}")
    channel = bot.get_channel(CHANNEL_ID)
    if channel:
        await send_verification_embed(channel)
        update_verified_count.start()

async def send_verification_embed(channel):
    view = discord.ui.View(timeout=None)

    class VerifyButton(discord.ui.Button):
        def __init__(self):
            label = config.get("verify_button_label", "Zweryfikuj się")
            style = STYLE_MAP.get(config.get("verify_button_style", "success").lower(), discord.ButtonStyle.success)
            super().__init__(label=label, style=style)

        async def callback(self, interaction):
            guild = bot.get_guild(GUILD_ID)
            member = guild.get_member(interaction.user.id)
            role = guild.get_role(VERIFIED_ROLE_ID)
            if member and role in member.roles:
                await interaction.response.send_message(config["dm_already_verified"], ephemeral=True)
                return


            code_id = generate_id()
            verification_map[interaction.user.id] = code_id
            link = VERIFICATION_URL.format(code_id)
            await interaction.user.send(config["dm_verification_prompt"].format(link=link))
            await interaction.response.send_message(config["dm_check_your_dm"], ephemeral=True)

    class VerifiedCounter(discord.ui.Button):
        def __init__(self):
            self.count = 0
            label = f"{config.get('verified_counter_prefix', 'Zweryfikowani')}: {self.count}"
            style = STYLE_MAP.get(config.get("verified_counter_style", "secondary").lower(), discord.ButtonStyle.secondary)
            super().__init__(label=label, style=style, disabled=True)

        async def update(self):
            guild = bot.get_guild(GUILD_ID)
            role = guild.get_role(VERIFIED_ROLE_ID)
            if role:
                self.count = len(role.members)
                self.label = f"{config.get('verified_counter_prefix', 'Zweryfikowani')}: {self.count}"

    verify_button = VerifyButton()
    counter_button = VerifiedCounter()
    await counter_button.update()

    view.add_item(verify_button)
    view.add_item(counter_button)
    view.counter_button = counter_button

    embed = discord.Embed(
        description=config["verification_embed_description"].format(bot_id=BOT_ID),
        color=discord.Color.purple()
    )
    embed.set_thumbnail(url=THUMBNAIL)

    await channel.send(embed=embed, view=view)
    bot.verification_view = view

@tasks.loop(minutes=1)
async def update_verified_count():
    view = getattr(bot, "verification_view", None)
    if view and hasattr(view, "counter_button"):
        await view.counter_button.update()
        for item in view.children:
            if isinstance(item, discord.ui.Button) and item.label.startswith(config.get("verified_counter_prefix", "Zweryfikowani")):
                item.label = view.counter_button.label

@bot.event
async def on_message(message):
    if message.author.bot:
        return

    if isinstance(message.channel, discord.DMChannel):
        user_id = message.author.id
        if user_id in verification_map:
            code_id = verification_map[user_id]
            backend_code = await get_code_from_backend(code_id)
            if backend_code and backend_code == message.content.strip():
                guild = bot.get_guild(GUILD_ID)
                member = guild.get_member(user_id)
                role = guild.get_role(VERIFIED_ROLE_ID)
                if member and role:
                    await member.add_roles(role)
                    await message.channel.send(config["dm_verified_success"])
                    del verification_map[user_id]
                else:
                    await message.channel.send(config["dm_verified_fail"])
            else:
                await message.channel.send(config["dm_wrong_code"])

    await bot.process_commands(message)

bot.run(TOKEN)
