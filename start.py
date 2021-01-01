# /usr/bin/python

import discord
from discord import channel
import schedule
import time
import random
import os
import asyncio
import threading
import json

TOKEN_PATH = './discord.token'
IMAGES_DIR_PATH = 'F:\\frens\\1.00'
CHANNEL_CONFIG_PATH = './channels.json'
CMD_WORD = '>pepe'

client = discord.Client()
sending_list = []
sending_list_change = False
command_list = []


@client.event
async def on_ready():
    print(f'Logged in as {client.user}.')
    await load_sending_list()
    print('loaded sending list')


@client.event
async def on_message(message):
    # Skip if the message is by the bot itself.
    if message.author == client.user:
        return

    if message.content.startswith(CMD_WORD):
        await process_command(message)


# Serializes the sending list a writes it into a json file
async def save_sending_list():
    serialized = json.dumps(sending_list, sort_keys=True, indent=4)
    with open(CHANNEL_CONFIG_PATH, 'w', encoding='utf-8') as file:
        file.write(serialized)


# Parses the channel json and sets it as `sending_list`
async def load_sending_list():
    global sending_list
    loaded = None
    try:
        with open(CHANNEL_CONFIG_PATH, 'r', encoding='utf-8') as file:
            loaded = json.loads(file.read())
    except FileNotFoundError as e:
        print(f'Sending list file was not found. Creating a new one.')
        await save_sending_list()
        return
    except json.decoder.JSONDecodeError:
        print('Invalid syntax in channels.json.')
        await save_sending_list()
        return
    if type(loaded) != list:
        print(loaded)
        print('Invalid structure of channels.json file')
        await save_sending_list()
        return
    sending_list = loaded
    print(sending_list)


# Calls an appropriate cmd fucntion given a message.
async def process_command(message):
    content = message.content.split(' ')[1:]
    if len(content) < 1:
        await cmd_help(None, message)
        return
    for command_entry in command_list:
        if content[0].lower() not in command_entry[1]:
            continue

        if command_entry[2]:
            if type(message.author) == discord.Member:
                if not message.author.guild_permissions.administrator:
                    print('Sorry kid. Admins only.')
                    continue

        await command_entry[0](content[1:], message)


# Obtains a path, opens it and feeds it to the channel specified.
async def send_random_picture(channel):
    opened = open(get_random_image_path(), 'rb')
    file = discord.File(opened)

    try:
        await channel.send(file=file)
    except Exception as e:
        print(e)


# Command that subscribes the channel id of the message to the sending list.
async def cmd_subscribe(content, message):
    global sending_list_change, sending_list

    channel_id = message.channel.id

    if channel_id in sending_list:
        await message.channel.send('This channel is already subbed dud.')
        return

    sending_list.append(channel_id)
    sending_list_change = True
    print(f'Channel {channel_id} joined the sending list.')
    await message.channel.send('Got ya.')


# Removes channel id of the message from the sending list.
async def cmd_unsubscribe(content, message):
    global sending_list_change, sending_list

    channel_id = message.channel.id

    for i, uid in enumerate(sending_list):
        if channel_id == uid:
            sending_list.pop(i)
            sending_list_change = True
            print(
                f'Channel {channel_id} was removed from the sending list.')
            await message.channel.send('K its gone.')
            return

    await message.channel.send('This channel isn\'t even subscribed.')


# Calls for a random image to be send in response.
async def cmd_send(content, message):
    print('send registered')
    await send_random_picture(message.channel)


# Pongs
async def cmd_ping(content, message):
    await message.channel.send('pong')


# Prints a help messge as a response.
async def cmd_help(content, message):
    mess = f'{client.user}\'s favourite word is ***{CMD_WORD}***.\n\n\
Use it with the following commands:\n\
**subscribe** - To subscribe the channel for daily pepe posting. *(admin only)*\n\
**unsubscribe** - To unsubscribe the channel from daily pepe posting. *(admin only)*\n\
btw. You can also message me directly to subscribe for a **personal daily** pepe feed.\n\
**pic** - To post a pepe pic (also available in DMs.)\n\n\
***WARNING** these are **wild** pepes! They may be **NSFW**! Use with coughtion.*'

    await message.channel.send(mess)


# Calls for a random image to be send to each subscriber.
async def send_to_subscribers():
    print('sending to subscribers')

    for id in sending_list:
        print(id)
        try:
            channel = await client.fetch_channel(id)
            await send_random_picture(channel)
        except Exception:
            print('Someting went wrong')


# If any changes have been made to sending list this will call for it beeing saved.
def start_sending_list_autosave():
    global sending_list_change

    if sending_list_change:
        sending_list_change = False
        asyncio.run_coroutine_threadsafe(save_sending_list(), client.loop)


# Starts the async task of sending. Used with the scheduler
def send_job():
    asyncio.run_coroutine_threadsafe(send_to_subscribers(), client.loop)


# Sets up the tasks and their timings
def start_schedule():
    schedule.every().day.at('07:00').do(send_job)
    # schedule.every(5).seconds.do(send_job)  # Debug
    schedule.every(1).minutes.do(start_sending_list_autosave)
    while True:
        schedule.run_pending()
        time.sleep(1)


# Picks a rondom file from the IMAGE_DIR_PATH
def get_random_image_path():
    n = 0
    rfile = None
    random.seed()
    for root, dirs, files in os.walk(IMAGES_DIR_PATH):
        for name in files:
            n = n+1
            if random.uniform(0, n) < 1:
                rfile = os.path.join(root, name)
    print(f'Random image is {rfile}')
    return rfile


# Returns the auth token at TOKEN_PATH
def get_token():
    global token
    with open(TOKEN_PATH, 'r', encoding='utf-8') as file:
        return file.read().strip().replace('\n', '')\
            .replace('\t', '')\
            .replace(' ', '')


# Creates command_list with the functions and their aliases
def init_command_list():
    global command_list
    command_list = [
        # Function      Aliases                     Require admin?
        [cmd_subscribe, ['subscribe', 'sub', 'add'], True],
        [cmd_unsubscribe, ['unsubscribe', 'unsub', 'remove'], True],
        [cmd_send, ['send', 'get', 'post', 'pic'], False],
        [cmd_ping, ['ping', 'pong'], False],
        [cmd_help, ['help'], False]
    ]


def main():
    init_command_list()
    # Starts the scheduling thread
    threading.Thread(target=start_schedule).start()
    # Starts the discord event loop
    client.run(get_token())


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print('interupted')
    except Exception:
        main()
