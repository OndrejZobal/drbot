#!/usr/bin/python

# Maybe I should have made this procedural well whatever. I wanted this to be
# just one file.

import time
import random
import os
import asyncio
import threading
import pathlib
import re
import toml

import discord
import schedule


class Channel:
    def __init__(self, id, allow_schedule_trigger=False, preferred_trigger_time=None, block_message_trigger=False):
        self.id = int(id)
        self.allow_schedule_trigger = allow_schedule_trigger
        self.preferred_trigger_time = preferred_trigger_time
        self.block_message_trigger = block_message_trigger

    def __repr__(self):
        return str(self.id)

class Trigger:
    def __init__(self, name):
        self.name = str(name)
        self.has_message_trigger = False
        self.has_schedule_trigger = False
        self.has_text_payload = False
        self.has_file_payload = False
        self.channels = []

    def set_message_trigger(self, pattern, subscribed_by_default):
        self.pattern = pattern
        self.subscripbed_by_default = subscribed_by_default
        self.has_message_trigger = True

    def set_schedule_trigger(self, date, time):
        self.date = date
        self.time = time
        self.has_schedule_trigger = True

    def set_payload_trigger(self, text_file, file_dir):
        if text_file != None:
            self.text_file = pathlib.Path(text_file)
            self.has_text_payload = True
        if file_dir != None:
            self.file_dir = file_dir
            self.has_file_payload = True

    def add_channel(self, channel):
        self.channels.append(channel)

    def __repr__(self):
        return self.name


TOKEN_PATH = './discord.token'
CONFIG_PATH = './config.toml'
#IMAGES_DIR_PATH = 'F:\\frens\\1.00' # TODO will be moved to 'plan.toml'.
CHANNEL_CONFIG_PATH = './channels.json' # Will be moved to channels.toml.
CMD_WORD = '>test' # TODO move to a config file.
PLAN_PATH = "plan.toml" # TODO move this eventually.
CHANNEL_PREFERENCE_PATH='channels.toml'
DEBUG = True

client = discord.Client()
sending_list = []
sending_list_change = False
command_list = []

trigger_list = []


@client.event
async def on_ready():
    print(f'Logged in as {client.user}.')
    await parse_channels(CHANNEL_PREFERENCE_PATH)
    print('loaded sending list')


async def send_text_message(channel, message):
    await channel.send(message)


async def send_random_message_from_file(channel, message_file):
    messages = None
    with open('message_file', 'r', encoding='utf-8') as file:
        messages = file.read()
    messages = messages.splitlines()
    await send_text_message(channel, random.choice(messages).replace('\\n',
                                                                     '\n'))


async def process_triggered_trigger(message, trigger, source):
    if trigger.file_dir is not None:
        await send_random_picture(message.channel, trigger.file_dir)
    if trigger.message_file is not None:
        await send_random_message_from_file(message.channel,
                                            trigger.message_file)
    print(f'A trigger {trigger.name} was just processed on channel'
          + f'{message.channel.id}. It was triggered by a {source}')


@client.event
async def on_message(message):
    # Skip if the message is by the bot itself.
    if message.author == client.user:
        return

    if message.content.startswith(CMD_WORD):
        await process_command(message)
        return

    if DEBUG: print(f'The trigger list: {trigger_list}')
    for trigger in trigger_list:
        if trigger.pattern != None:
            if DEBUG: print(f'The trigger {trigger.pattern}')
            if re.search(trigger.pattern, message.content):
                if DEBUG: print('reacting')
                await process_triggered_trigger(message, trigger, "message")
                return


def get_plan_paths():
    # TODO Maybe add some cool logic I dunno.
    return [PLAN_PATH]


def parse_plan(path):
    global trigger_list
    # Converting each entry into a trigger object.
    trigg_list = []
    for file in get_plan_paths():
        # Using a random library to parse it.
        toml_dict = toml.load(path)
        for i, entry in enumerate(toml_dict):
            trigger = Trigger(str(entry))
            trigger.pattern = toml_dict[entry].get('message').get('trigger')
            trigger.schedule_time = toml_dict[entry].get('schedule').get('time')
            trigger.schedule_date = toml_dict[entry].get('schedule').get('date')
            trigger.file_dir = toml_dict[entry].get('payload').get('file_dir')
            trigger.message_file = toml_dict[entry].get('payload').get('message_file')
            trigg_list.append(trigger)

    print("Trigger list has been reloaded")
    print(f'Total count of triggers is: {len(trigg_list)}')
    # TODO actualy set this shit in the function.
    # Returning all Trigger objects in a list.
    trigger_list = trigg_list
    rebuild_schedule()


async def parse_channels(path):
    global trigger_list
    print(f'Parsing channel preferences from {path}')
    toml_dict = toml.load(path)
    for trigger in trigger_list:
        sub_entries = toml_dict.get(trigger.name)
        for sub_entry in sub_entries['channel']:
            if sub_entry:
                channel = Channel(sub_entry.get('id'))
                channel.allow_schedule_trigger = sub_entry.get('allow_schedule_trigger')
                channel.preferred_trigger_time = sub_entry.get('preferred_trigger_time')
                channel.block_message_trigger = sub_entry.get('block_message_trigger')
                trigger.add_channel(channel)


async def serialize_channels(path):
    print('Starting serializing channels.')
    new_dict = {}
    for trigger in trigger_list:
        new_dict_list = []
        for channel in trigger.channels:
            new_new_dict = {}
            new_new_dict['id'] = channel.id
            new_new_dict['allow_schedule_trigger'] = channel.allow_schedule_trigger
            new_new_dict['preferred_trigger_time'] = channel.preferred_trigger_time
            new_new_dict['block_message_trigger'] = channel.block_message_trigger
            new_dict_list.append(new_new_dict)
        new_dict[trigger.name] = {}
        new_dict[trigger.name]['channel'] = new_dict_list
    print(f'Writing channels to {path}.')
    with open(path, 'w', encoding='utf-8') as file:
        file.write(toml.dumps(new_dict))
    print('Channels saved successfully.')


# Serializes the sending list a writes it into a json file
async def save_sending_list():
    serialized = json.dumps(sending_list, sort_keys=True, indent=4)
    with open(CHANNEL_CONFIG_PATH, 'w', encoding='utf-8') as file:
        file.write(serialized)


# Calls an appropriate cmd function given a message.
async def process_command(message):
    # Splits the message and cuts the original command.
    content = message.content.split(' ')[1:]
    # Print help if nothing follows the CMD_WORD.
    if len(content) < 1:
        await cmd_help(None, message)
        return

    command_found = False
    for command_entry in command_list:
        # If it's not a valid command continue.
        if content[0].lower() not in command_entry[1]:
            continue

        command_found = True
        # Make sure the message was not sent by this bot and that the issuer
        # is admin if the command requires them.
        if command_entry[2]:
            if type(message.author) == discord.Member:
                if not message.author.guild_permissions.administrator:
                    if DEBUG: print(f'User {message.author.id} issued a command outside of it\'s permissions in '
                                    + f'channel {message.channel.id}. Command: {content[1]}')
                    await message.channel.send('Sorry kid. Admins only.')
                    continue

        if DEBUG:
            await command_entry[0](content[1:], message)
        else:
            try:
                await command_entry[0](content[1:], message)
            except Exception as e:
                print(f'An exception has occoured while processing a command {content[1]}: {e.with_traceback()}')

    if not command_found:
        await message.channel.send(f'Sorry, *"{content[0]}"* is not a known command.')

# Obtains a path, opens it and feeds it to the channel specified.
async def send_random_picture(channel, images_dir):
    opened = open(get_random_image_path(images_dir), 'rb')
    file = discord.File(opened)

    await channel.send(file=file)


# Command that subscribes the channel id of the message to the sending list.
async def cmd_subscribe(content, message):
    global sending_list_change, sending_list

    def test_time(string):
        return bool()

    channel_id = message.channel.id

    print(content)
    if len(content) < 1:
        print('Message does not contain the name of the trigger.')
        return

    # FAQ: Seems like there is a lot of searching with nested loops...
    #      Wouldn't it be better to restructure the data into hashmaps?
    # A:   😳.

    # Check if passed argument is a valid trigger entry.
    for trigger in trigger_list:
        # Check if the trigger name exists.
        if trigger.name == content[0]:
            # Check if entry for this channel exists.
            already_subscribed = False
            located_channel = None
            for channel in trigger.channels:
                if channel.id == channel_id:
                    located_channel = channel
                    already_subscribed = True
                    break

            # Create the channel entry if it didn't exist before.
            if located_channel == None:
                located_channel = Channel(channel_id)
                located_channel.block_message_trigger = False
                located_channel.allow_schedule_trigger = False

            # Process the time argument.
            if len(content) >= 2:
                # Verify that the time is in the correct format.
                #   The reason why I am using regex to verify the format instead
                #   of just trying to parse the numbers, is to flex.
                if not re.match('^(0[0-9]|1[0-9]|2[0-4]):[0-5][0-9]$', content[1]):
                    print('Wrong time format')
                    return
                located_channel.preferred_trigger_time = content[1]
                sending_list_change = True

                if already_subscribed:
                    print(f'Time changed to {content[1]}.')


            # Inform the user that the channel was already subscribed.
            # The user will not be informed about this if they are just changing
            # the time of scheduled trigger.
            elif already_subscribed:
                # In case time preferred time used is registered but the user
                # registered the channel without specifying time, the time gets
                # cleared.
                if len(content) <= 1:
                    located_channel.preferred_trigger_time = None
                    sending_list_change = True
                    print('Preferred time cleared.')
                else:
                    print('Already subbed.')
                return

            # This is where the channel gets actually saved.
            if not already_subscribed:
                trigger.channels.append(located_channel)
                sending_list_change = True
                print(f'Channel: {channel_id} was just subscribed to {trigger}')
                return
        break

    '''
    if channel_id in sending_list:
        await message.channel.send('This channel is already subbed dud.')
        return

    sending_list.append(channel_id)
    sending_list_change = True
    print(f'Channel {channel_id} joined the sending list.')
    await message.channel.send('Got ya.')
    '''


# Removes channel id of the message from the sending list.
async def cmd_unsubscribe(content, message):
    global sending_list_change

    channel_id = message.channel.id

    if len(content) < 1:
        print('Message does not contain the name of the trigger.')
        return

    trigger_found = False
    for trigger in trigger_list:
        print(f'trigger.name {trigger.name} contetnt {content[0]}')
        if trigger.name != content[0]:
            continue

        if trigger.name == content[0]:
            print('Big POG')

        trigger_found = True
        for i, channel in enumerate(trigger.channels):
            if channel.id == channel_id:
                trigger.channels.pop(i)
                sending_list_change = True
                print(f'Channel {channel_id} removed from the list')
                return
            else:
                print('Channel was not subbed to this trigger.')
        break

    if not trigger_found:
        print(f'Trigger {content[0]} was not found.')

    '''
    for i, uid in enumerate(sending_list):
        if channel_id == uid:
            sending_list.pop(i)
            sending_list_change = True
            print(
                f'Channel {channel_id} was removed from the sending list.')
            await message.channel.send('K its gone.')
            return

    await message.channel.send('This channel isn\'t even subscribed.')
    '''


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
async def send_to_subscribers(trigger):
    print('sending to subscribers')

    # TODO Use data from new channels.toml
    for channel in trigger.channels:
        if channel.allow_schedule_trigger:
            try:
                channel = await client.fetch_channel(channel.id)
                await send_random_picture(channel, trigger.file_dir)
            except Exception:
                print('Someting went wrong')


# If any changes have been made to sending list this will call for it being
# saved.
def start_sending_list_autosave():
    global sending_list_change

    if sending_list_change:
        sending_list_change = False
        asyncio.run_coroutine_threadsafe(serialize_channels(CHANNEL_PREFERENCE_PATH), client.loop)


# Starts the async task of sending. Used with the scheduler
def send_job(trigger):
    asyncio.run_coroutine_threadsafe(send_to_subscribers(trigger), client.loop)


def rebuild_schedule():
    # Remove all jobs
    schedule.clear()
    schedule.every(1).minutes.do(start_sending_list_autosave)

    # Loop through all triggers
    for trigger in trigger_list:
        # Find schedule triggers
        if trigger.has_schedule_trigger:
            # TODO Parse the datetime values
            # Add the trigger
            schedule.every.day.at(trigger.time).do(send_job, trigger)


# Sets up the tasks and their timings
def set_schedule():
    global trigger_list
    parse_plan(get_plan_paths())
    while True:
        # TODO check for plan updates and update schedules.
        schedule.run_pending()
        time.sleep(1)


# Picks a random file from the 'directory'
def get_random_image_path(directory):
    n = 0
    rfile = None
    random.seed()
    for root, dirs, files in os.walk(directory):
        for name in files:
            n = n+1
            if random.uniform(0, n) < 1:
                rfile = os.path.join(root, name)
    print(f'Random image is {rfile}')
    return rfile


# Returns the auth token at TOKEN_PATH
def get_token():
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
        [cmd_ping, ['ping', 'pong'], False],
        [cmd_help, ['help'], False]
    ]


def main():
    init_command_list()
    # TODO load triggers.
    # Starts the scheduling thread
    threading.Thread(target=set_schedule).start()
    # Starts the discord event loop
    client.run(get_token())


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print('interupted')
    except Exception:
        main()
