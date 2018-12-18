#!python3.6
"""
Dayvidbot.py

Runs continuously until stopped manually or disconnected from WebSocket for any reason.
Requires pyt

https://discordapp.com/oauth2/authorize?scope=bot&permissions=67648&client_id=524460491565694991
"""

import asyncio
import json
import os
import random
import re

import aiohttp

TOKEN = os.getenv("TOKEN")
URL = "https://discordapp.com/api"
DAYVID_STRING_REGEX = re.compile(r"da(y)+vid", re.I)

DAVID_STRING_TO_MESSAGE_PREFIX_MAPPING = [
    (
        ["david"],
        [
            "{david_string}!",
            "Ah, my ole' fern {david_string}!",
            "What a good ole' Toronno boy that {david_string} is, innhe?",
        ],
    ),
    (
        ["leg", "legman", "legrnan"],
        [
            "Do you perhaps mean {david_string}, {author}?",
            "{author}, I think you mean {david_string}.",
        ],
    ),
]

EMOJI_REACTION_POSSIBILITIES = [
    "🤤",
    "🔥"
]


def generate_random_david_string():
    return f"DA{'Y' * random.randint(1, 10)}VID"


async def api_call(path, method="GET", **kwargs):
    """Return the JSON body of a call to Discord REST API."""
    defaults = {"headers": {"Authorization": f"Bot {TOKEN}"}}
    kwargs = dict(defaults, **kwargs)
    async with aiohttp.ClientSession() as session:
        async with session.request(method, f"{URL}{path}", **kwargs) as response:
            assert 200 <= response.status <= 299, response.reason
            if "json" in response.headers["Content-Type"]:
                return await response.json()
            else:
                return await response.text()


async def add_reaction(channel_id, message_id, reaction_emoji):
    print(
        f"About to reaction to message ID ({message_id}) in channel ({channel_id}) using emoji ({reaction_emoji})."
    )
    return await api_call(
        f"/channels/{channel_id}/messages/{message_id}/reactions/{reaction_emoji}/@me",
        "PUT",
    )


async def send_message(channel_id, content):
    """Send a message with content to the channel_id."""
    print(f"About to send message: {content}")
    return await api_call(
        f"/channels/{channel_id}/messages", "POST", json={"content": content}
    )


async def heartbeat(ws, interval, last_sequence):
    """Send every interval ms the heatbeat message."""
    while True:
        await asyncio.sleep(interval / 1000)  # seconds
        await ws.send_json({"op": 1, "d": last_sequence})  # Heartbeat


async def start(url):
    async with aiohttp.ClientSession() as session:
        async with session.ws_connect(f"{url}?v=6&encoding=json") as ws:
            async for msg in ws:
                data = json.loads(msg.data)
                if data["op"] == 10:  # Hello
                    # Send identification response
                    await ws.send_json(
                        {
                            "op": 2,  # Identify
                            "d": {
                                "token": TOKEN,
                                "properties": {},
                                "compress": False,
                                "large_threshold": 250,
                            },
                        }
                    )
                    last_sequence = data["s"]
                    print(json.dumps(data, indent=2))
                    # Set up async task for responding to heartbeat within interval
                    asyncio.ensure_future(
                        heartbeat(ws, data["d"]["heartbeat_interval"], last_sequence)
                    )
                elif data["op"] == 11:  # Heartbeat ACK
                    pass
                elif data["op"] == 0:  # Dispatch
                    if data["t"] == "MESSAGE_CREATE":
                        print("DATA: " + json.dumps(data["d"], indent=2))
                        created_message = data["d"]["content"].lower()
                        channel_id = data["d"]["channel_id"]
                        author = data["d"]["author"]["username"]
                        message_id = data["d"]["id"]
                        # Don't fall over ourselves, let's not react to ourselves.
                        if author == "DayvidBot":
                            continue

                        # React to people that use Dayvid's name properly
                        if DAYVID_STRING_REGEX.search(created_message) is not None:
                            await add_reaction(channel_id, message_id, random.choice(EMOJI_REACTION_POSSIBILITIES))
                            continue

                        # Otherwise we need to correct people
                        for (
                            string_check_list,
                            message_poss,
                        ) in DAVID_STRING_TO_MESSAGE_PREFIX_MAPPING:
                            if any(x in created_message for x in string_check_list):
                                full_message = random.choice(message_poss)
                                full_message = full_message.format(
                                    david_string=generate_random_david_string(),
                                    author=author,
                                )
                                await send_message(channel_id, full_message)
                                break
                else:
                    pass


async def main():
    """Main program."""
    response = await api_call("/gateway")
    await start(response["url"])


loop = asyncio.get_event_loop()
loop.run_until_complete(main())
loop.close()
