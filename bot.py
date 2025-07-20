import threading
from flask import Flask
import discord
from discord import app_commands
from discord.ext import commands
from yt_dlp import YoutubeDL
from youtubesearchpython import VideosSearch

# --- Flask keep-alive server ---
app = Flask(__name__)

@app.route("/")
def home():
    return "Bot działa!"

def run_flask():
    app.run(host="0.0.0.0", port=8080)

# --- Discord bot ---
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='!', intents=intents)

YDL_OPTIONS = {'format': 'bestaudio', 'noplaylist': 'True'}
loop_states = {}
playing_states = {}

class MusicView(discord.ui.View):
    def __init__(self, interaction, url, title):
        super().__init__(timeout=None)
        self.interaction = interaction
        self.url = url
        self.title = title
        self.is_looping = False

    @discord.ui.button(label="Loop", style=discord.ButtonStyle.primary, custom_id="loop_button")
    async def loop(self, interaction: discord.Interaction, button: discord.ui.Button):
        guild = interaction.guild
        if guild is None:
            await interaction.response.send_message("Nie można ustalić serwera.", ephemeral=True)
            return
        prev_loop = loop_states.get(guild.id, False)
        self.is_looping = not prev_loop
        loop_states[guild.id] = self.is_looping
        await interaction.response.send_message(
            f"{'Włączono' if self.is_looping else 'Wyłączono'} zapętlanie.", ephemeral=True
        )

    @discord.ui.button(label="Stop", style=discord.ButtonStyle.danger, custom_id="stop_button")
    async def stop(self, interaction: discord.Interaction, button: discord.ui.Button):
        guild = interaction.guild
        if guild is not None and guild.voice_client:
            await guild.voice_client.disconnect(force=True)
            loop_states[guild.id] = False
            playing_states[guild.id] = False
            await interaction.response.send_message("Muzyka zatrzymana, bot wyszedł z kanału.", ephemeral=True)
        else:
            await interaction.response.send_message("Bot nie jest na kanale głosowym.", ephemeral=True)

def get_audio_url(url):
    with YoutubeDL(YDL_OPTIONS) as ydl:
        info = ydl.extract_info(url, download=False)
        return info['url'], info.get('title', 'Nieznany tytuł')

async def play_audio_interaction(interaction, url, title):
    user = interaction.user
    if not user.voice or not user.voice.channel:
        await interaction.followup.send("Musisz być na kanale głosowym!", ephemeral=True)
        return
    channel = user.voice.channel
    guild = interaction.guild
    if guild is None:
        await interaction.followup.send("Nie można ustalić serwera.", ephemeral=True)
        return
    voice_client = guild.voice_client
    if voice_client is None:
        voice_client = await channel.connect()
    else:
        await voice_client.move_to(channel)

    audio_url, _ = get_audio_url(url)
    source = discord.FFmpegPCMAudio(audio_url, options='-vn')
    playing_states[guild.id] = True

    async def after_playing(error):
        if guild is not None and loop_states.get(guild.id, False) and playing_states.get(guild.id, True):
            voice_client.play(discord.FFmpegPCMAudio(audio_url, options='-vn'), after=lambda e: bot.loop.create_task(after_playing(e)))
        else:
            playing_states[guild.id] = False
            await voice_client.disconnect(force=True)

    voice_client.stop()
    voice_client.play(source, after=lambda e: bot.loop.create_task(after_playing(e)))

    embed = discord.Embed(title=title, url=url, description="Kliknij tytuł, aby przejść do utworu.")
    view = MusicView(interaction, url, title)
    await interaction.followup.send(embed=embed, view=view)

@bot.tree.command(name="send", description="Wyszukaj i odtwórz muzykę po tytule")
@app_commands.describe(search="Tytuł lub fraza do wyszukania na YouTube")
async def send_slash(interaction: discord.Interaction, search: str):
    await interaction.response.defer()
    videosSearch = VideosSearch(search, limit=1)
    result = videosSearch.result()
    if not isinstance(result, dict) or 'result' not in result or not result['result']:
        await interaction.followup.send("Nie znaleziono utworu.")
        return
    url = result['result'][0]['link']
    title = result['result'][0]['title']
    await play_audio_interaction(interaction, url, title)

@bot.tree.command(name="link", description="Odtwórz muzykę z podanego linku YouTube")
@app_commands.describe(url="Link do utworu na YouTube")
async def link_slash(interaction: discord.Interaction, url: str):
    await interaction.response.defer()
    audio_url, title = get_audio_url(url)
    await play_audio_interaction(interaction, url, title)

@bot.event
async def on_ready():
    await bot.tree.sync()
    print(f"Zalogowano jako {bot.user}")

if __name__ == "__main__":
    threading.Thread(target=run_flask, daemon=True).start()
    bot.run('MTM5NjQ5MTQzNTY4MjgyODQ5MQ.GIqhTZ.yxAxC6jeRNL4Cuj8nX6GtFM4m2go9Tm9nXuVI4')
