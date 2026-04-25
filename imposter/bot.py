import discord
from discord.ext import commands
import difflib
import re
import aiohttp
from PIL import Image
import imagehash
import io
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# --- CONFIGURATION ---
TOKEN = os.getenv('DISCORD_BOT_TOKEN')
try:
    protected_users_env = os.getenv('PROTECTED_USER_IDS', '')
    if protected_users_env:
        PROTECTED_USER_IDS = [int(u_id.strip()) for u_id in protected_users_env.split(',')]
    else:
        PROTECTED_USER_IDS = []
    
    ADMIN_CHANNEL_ID = int(os.getenv('ADMIN_CHANNEL_ID', 0))
    QUARANTINE_ROLE_ID = int(os.getenv('QUARANTINE_ROLE_ID', 0))
except ValueError:
    print("Error: Ensure your IDs in the .env file are valid numbers (separated by commas for user IDs).")
    exit(1)

SIMILARITY_THRESHOLD = float(os.getenv('SIMILARITY_THRESHOLD', '0.80'))
# ---------------------

intents = discord.Intents.default()
intents.members = True
intents.presences = True
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)

def normalize_string(text):
    """Cleans up text to catch sneaky variations"""
    if not text:
        return ""
    text = text.lower()
    text = re.sub(r'[^a-z0-9]', '', text)
    # Replace common look-alikes
    text = text.replace('0', 'o').replace('1', 'l').replace('i', 'l').replace('rn', 'm')
    return text

def check_name_similarity(name1, name2):
    """Returns a similarity ratio between 0.0 and 1.0"""
    norm1 = normalize_string(name1)
    norm2 = normalize_string(name2)
    return difflib.SequenceMatcher(None, norm1, norm2).ratio()

async def get_image_hash(url):
    """Downloads an image and generates a perceptual hash"""
    if not url:
        return None
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(str(url)) as resp:
                if resp.status == 200:
                    data = await resp.read()
                    img = Image.open(io.BytesIO(data))
                    return imagehash.average_hash(img)
    except Exception as e:
        print(f"Failed to hash image: {e}")
    return None

async def investigate_user(member):
    """Core logic to check if a user is an impersonator"""
    if member.id in PROTECTED_USER_IDS or member.bot:
        return

    admin_channel = member.guild.get_channel(ADMIN_CHANNEL_ID)
    quarantine_role = member.guild.get_role(QUARANTINE_ROLE_ID)

    reasons = []

    for protected_id in PROTECTED_USER_IDS:
        protected_member = member.guild.get_member(protected_id)
        if not protected_member:
            continue
            
        # 1. Check Display Name
        name_similarity = check_name_similarity(member.display_name, protected_member.display_name)
        if name_similarity >= SIMILARITY_THRESHOLD:
            reasons.append(f"Name is {int(name_similarity * 100)}% similar to {protected_member.name}.")

        # 2. Check Profile Picture
        if member.avatar and protected_member.avatar:
            suspect_hash = await get_image_hash(member.avatar.url)
            real_hash = await get_image_hash(protected_member.avatar.url)
            
            if suspect_hash and real_hash:
                hash_diff = suspect_hash - real_hash 
                if hash_diff <= 5:
                    reasons.append(f"Profile picture visually matches {protected_member.name} (Difference: {hash_diff}).")

    # 3. Take Action if flagged
    if reasons:
        if quarantine_role:
            try:
                await member.add_roles(quarantine_role, reason="Suspected Impersonation")
            except discord.Forbidden:
                print(f"Missing permissions to add quarantine role to {member.name}.")

        embed = discord.Embed(
            title="⚠️ Potential Impersonator Detected", 
            color=discord.Color.red()
        )
        embed.add_field(name="Suspect", value=f"{member.mention} ({member.id})", inline=False)
        embed.add_field(name="Reasons", value="\n".join(reasons), inline=False)
        if member.avatar:
            embed.set_thumbnail(url=member.avatar.url)
        
        if admin_channel:
            await admin_channel.send(embed=embed)

@bot.event
async def on_ready():
    print(f"✅ Shield Bot activated as {bot.user}")
    if not PROTECTED_USER_IDS:
        print("WARNING: PROTECTED_USER_IDS is empty. Please set it in your .env file.")

@bot.event
async def on_member_join(member):
    await investigate_user(member)

@bot.event
async def on_member_update(before, after):
    if before.display_name != after.display_name or before.avatar != after.avatar:
        await investigate_user(after)

if __name__ == '__main__':
    if not TOKEN:
        print("Error: DISCORD_BOT_TOKEN not found. Please add it to your .env file.")
    else:
        bot.run(TOKEN)
