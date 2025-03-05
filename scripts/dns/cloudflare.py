import asyncio
import json
import httpx
import os
import time
import sys
from discord import Intents, Client, Message
from dotenv import load_dotenv

load_dotenv(".env")

CLOUDFLARE_TOKEN = os.environ.get('CLOUDFLARE_TOKEN')
CLOUDFLARE_ZONE = os.environ.get('CLOUDFLARE_ZONE')
DNS_RECORD_TO_UPDATE = os.environ.get('DNS_RECORD_TO_UPDATE')
MY_EMAIL = os.environ.get('MY_EMAIL')

GW_PREVIOUS_IP: str = os.environ.get('GW_PREVIOUS_IP')

DISCORD_TOKEN = os.environ.get("DISCORD_TOKEN")
DISCORD_CHANNEL_ID_ERRORS = os.environ.get("DISCORD_CHANNEL_ID_ERRORS")
DISCORD_CHANNEL_ID_LOGS = os.environ.get("DISCORD_CHANNEL_ID_LOGS")

LOG_FILE = os.environ.get("LOG_FILE")

HEADER = {
    "Authorization": f"Bearer {CLOUDFLARE_TOKEN}",
    "x-auth-email": f"{MY_EMAIL}",
    "Content-Type": "application/json"
}

intents = Intents.default()
intents.message_content = True
client = Client(intents=intents)


async def token_validation() -> None:
    VERIFY_URL = "https://api.cloudflare.com/client/v4/user/tokens/verify"
    request = httpx.get(VERIFY_URL, headers=HEADER)
    if request.status_code != 200:
        await send_error_logs(f"cloudflare.py: Cloudflare API Token invalid or API endpoint not responding! 👀 ```{request.text}```")
        sys.exit()

async def get_record_id() -> str:
    DNS_LIST_URL = f"https://api.cloudflare.com/client/v4/zones/{CLOUDFLARE_ZONE}/dns_records"
    request = httpx.get(DNS_LIST_URL, headers=HEADER)
    
    if request.status_code != 200:
         await send_error_logs(f"cloudflare.py: Cloudflare API Token invalid or API endpoint not responding! 🤌 ```{request.text}```")
         sys.exit() 
    
    records = request.json()['result']
    for r in records:
        if r['name'] == DNS_RECORD_TO_UPDATE:
            return r['id']


async def get_current_ip() -> str:
    IP_URL = "https://ifconfig.me/all.json"
    request = httpx.get(IP_URL)
    
    if request.status_code != 200:
        await send_error_logs(f"cloudflare.py: Could not fetch IP from ifconfig.me! 🫵 ```{request.text}```")
        sys.exit()
        
    return request.json()['ip_addr']


async def update_record(gw_ip: str, record_id: str) -> None:
    DNS_URL = f"https://api.cloudflare.com/client/v4/zones/{CLOUDFLARE_ZONE}/dns_records/{record_id}"
    DATA = {
        "type": "A",
        "name": f"{DNS_RECORD_TO_UPDATE}",
        "content": f"{gw_ip}",
        "ttl": 3600,
        "proxied": False
    }
    request = httpx.put(DNS_URL, headers=HEADER, json=DATA)
    if request.status_code != 200:
        await send_error_logs(f"cloudflare.py: Cloudflare API Token invalid or API endpoint not responding! 🤷‍♂️ ```{request.text}```")
        sys.exit()
    
    await send_logs(f"cloudflare.py: \nUpdated {DNS_RECORD_TO_UPDATE} with ip: {gw_ip}")

async def update_previous_ip(gw_ip) -> None:
    os.environ["GW_PREVIOUS_IP"] = gw_ip

    with open(".env", "r") as file:
        lines = file.readlines()

    with open(".env", "w") as file:
        for line in lines:
            if line.startswith("GW_PREVIOUS_IP="):
                file.write(f"GW_PREVIOUS_IP={gw_ip}\n")
            else:
                file.write(line)    
    return

@client.event
async def on_ready():
    print(f'We have logged in as {client.user}')
    gw_ip = await get_current_ip()

    if gw_ip != GW_PREVIOUS_IP:
        await token_validation()
        record_id = await get_record_id()
        await update_record(gw_ip, record_id)
        await update_previous_ip(gw_ip)
        sys.exit()
    
    await send_logs(f"cloudflare.py: No updates needed")
    sys.exit()

@client.event
async def send_logs(message: Message) -> None:
    try: 
        channel = client.get_channel(int(DISCORD_CHANNEL_ID_LOGS))
        await channel.send(message)
    except Exception as e:
        print(e)

@client.event
async def send_error_logs(message: Message) -> None:
    try: 
        channel = client.get_channel(int(DISCORD_CHANNEL_ID_ERRORS))
        await channel.send(message)
    except Exception as e:
        print(e)

if __name__ == "__main__":
    
    required_env_vars = ["CLOUDFLARE_TOKEN", "CLOUDFLARE_ZONE", "DNS_RECORD_TO_UPDATE", "MY_EMAIL", "DISCORD_TOKEN", "DISCORD_CHANNEL_ID_ERRORS", "DISCORD_CHANNEL_ID_LOGS", "GW_PREVIOUS_IP"]
    for var in required_env_vars:
        if not os.environ.get(var):
            raise EnvironmentError(f"Environment variable {var} is not set.")

    client.run(DISCORD_TOKEN)
