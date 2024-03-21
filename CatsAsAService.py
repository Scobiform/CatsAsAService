import os
import threading
import time
import logging
import datetime
import json
import asyncio
import aiofiles
from threading import Thread
from datetime import date
from concurrent.futures import ThreadPoolExecutor
from quart import Quart, render_template, websocket, render_template_string, request, jsonify
from mastodon import Mastodon
from mastodon.streaming import StreamListener, CallbackStreamListener
from mastodon.Mastodon import MastodonMalformedEventError, MastodonBadGatewayError, MastodonServiceUnavailableError, MastodonNetworkError, MastodonAPIError, MastodonInternalServerError, MastodonIllegalArgumentError

# CatsAsAService (CaaS)
# AGPLv3 License

# The web interface will allow you to monitor messages from mastodon and the bot, 
# start and stop the bot, change settings, and organize the content archive
# http://localhost:5000

# Requirements:
# Mastodon.py (pip install Mastodon.py) - MIT License - https://github.com/halcy/Mastodon.py
# Mastodon.py documentation: https://mastodonpy.readthedocs.io/en/stable/
# Quart (pip install Quart) - BSD License - https://github.com/pallets/Quart
# Quart documentation: https://Quart.palletsprojects.com/en/3.0.x/

# Configuration
config = {}

# Setting up threads
tasks = [] # List of threads we will start

# Load the configuration from the settings.json file
def load_config():
    try:
        with open('settings.json', 'r', encoding='utf-8') as config_file:
            config = json.load(config_file)
            print("Configuration loaded successfully.")
            return config
    except FileNotFoundError:
        print("settings.json file not found.")
    except json.JSONDecodeError as e:
        print(f"An error occurred while decoding settings.json: {e}")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
    return {}

# Load the configuration
config = load_config()

# Mastodon configuration
app_name = config['app_name']
instance_url = config['instance_url']
email = config['email']
password = config['password']

# UI configuration
heartbeatIcon = config['heartbeatIcon']

# Bot Settings
cancel_token = threading.Event() # Cancellation token

# Configure logging based on the JSON settings
logging_config = config['logging']
logging.basicConfig(
    filename=logging_config['filename'],
    filemode='a',
    format=logging_config['format'],
    level=getattr(logging, logging_config['level'])
)

# Hashtags to listen to
hashtags = config['hashtags']

# bad words, hashtags, and accounts
bad_words = config['bad_words']
bad_hashtags = config['bad_hashtags']
bad_accounts = config['bad_accounts']

# Post content and interval
postContent = config['postContent']
interval = config['interval']

# Save configuration
def update_config(configuraion, new_data):
    # Update the existing configuration with new data
    configuraion.update(new_data)
    # Save the updated configuration back to the file
    with open('settings.json', 'w', encoding='utf-8') as config_file:
        json.dump(configuraion, config_file, indent=4)

# Quart app
app = Quart(__name__)
connections = set()

# Create Mastodon app and get user credentials
def create_secrets():
    # Create the secrets files if they don't exist
    create_file('clientcred.secret')
    create_file('usercred.secret')

    # Create Mastodon app (client credentials)
    Mastodon.create_app(
        app_name,
        api_base_url=instance_url,
        to_file='clientcred.secret'
    )

    # Initialize Mastodon with client credentials
    mastodon = Mastodon(
        client_id='clientcred.secret',
        api_base_url=instance_url
    )

    # Log in and save user credentials
    mastodon.log_in(
        email,
        password,
        to_file='usercred.secret'
    )

# If secrets are not present, create them
def check_for_secrets():
    if os.path.exists('usercred.secret'):
        print("Secrets found.")
    else:
        print("Secrets not found.")
        create_secrets()

# Create a file if it doesn't exist
def create_file(file_name):
    try:
        with open(file_name, 'a'):
            pass
        print(f"File '{file_name}' created successfully.")
    except Exception as e:
        print(f"Error creating '{file_name}': {e}")

# Hashtag Listener
class HashtagListener(StreamListener):
    # Constructor
    def __init__(self, mastodon_instance, loop):
        self.mastodon = mastodon_instance
        self.loop = loop
        self.heartbeatIcon = config['heartbeatIcon']

    # Called when a new status arrives
    def on_update(self, status):
        # Skip counter - if it's 0, the status will be boosted
        skipCounter = 0  
        
        try:
            if status.account.username == self.mastodon.me().username:
                logging.info('....skipped')
            if status.account.username != self.mastodon.me().username:
                # Check if the account is a bot
                if status.account.bot == True:
                    logging.info('....bot - skipped')
                    skipCounter += 1
                if status.account.bot == False:
                    # Check if there is media
                    if len(status.media_attachments) == 0:
                        logging.info('no media - skipped')
                        skipCounter += 1
                    # # Check if there is alt text
                    # for media in status.media_attachments:
                    #     # Skip if no Alt Text
                    #     if not media.description:
                    #         logging.info('....no alt text - skipped')
                    #         skipCounter += 1
                    # # Skip if too many hashtags
                    # if len(status.tags) > 9:
                    #     logging.info('....too many hashtags - skipped')
                    #     skipCounter += 1
                    # Check if there is a bad account
                    for account in bad_accounts:
                        if account == status.account.username:
                            logging.info('badaccount found - skipped')
                            skipCounter += 1
                    # Check if there is a bad word
                    for word in bad_words:
                         if word in status.content:
                             logging.info('badword found - skipped')
                             skipCounter += 1
                    # Check if there is a bad hashtag
                    for hashtag in bad_hashtags:
                         for tag in status.tags:
                             if hashtag == tag['name']:
                                 logging.info('badhashtag found - skipped')
                                 skipCounter += 1
                    # Only boost if skipCounter is 0
                    if skipCounter == 0:
                        if str(status.in_reply_to_account_id) == 'None':
                            #self.mastodon.status_reblog(status.id)
                            #self.mastodon.status_favourite(status.id)
                            for media in status.media_attachments:
                                if media.type == "image":
                                    message = f"<a href='{status.url}' target='_blank'><img src='{media.url}' alt='{media.description}' /></a>"
                                    asyncio.run_coroutine_threadsafe(broadcast_message(message), self.loop)
                                    logging.info('....image boosted')
                                if media.type == "video":
                                    message = f"<video src='{media.url}' controls />"
                                    asyncio.run_coroutine_threadsafe(broadcast_message(message), self.loop)
                                    logging.info('....video boosted')
            # Set skipCounter to 0
            skipCounter = 0
        except MastodonInternalServerError as errorcode:
            logging.error("MastodonInternalServerError:" + str(errorcode))
        except MastodonServiceUnavailableError as errorcode:
            logging.error("MastodonServiceUnavailableError: " + str(errorcode))
        except MastodonBadGatewayError as errorcode:
            logging.error("MastodonBadGatewayError: " + str(errorcode))
        except MastodonMalformedEventError as errorcode:
            logging.error("MastodonMalformedEventError: " + str(errorcode))
        except MastodonNetworkError as errorcode:
            logging.error("MastodonNetworkError: " + str(errorcode))
        except MastodonAPIError as errorcode:
            logging.error("MastodonAPIError: " + str(errorcode))
        except MastodonIllegalArgumentError as errorcode:
            logging.error("MastodonIllegalArgumentError:" + str(errorcode))
        except Exception as errorcode:
            logging.error("ERROR: " + str(errorcode))
            
    # Called when a heartbeat arrives
    def handle_heartbeat(self):
        try:
            message = self.heartbeatIcon
            asyncio.run_coroutine_threadsafe(broadcast_message(message), self.loop)
        except Exception as errorcode:
            logging.error("ERROR: " + str(errorcode))
            return
        return

# Content tooting
async def toot_content(mastodon, interval):
    '''This function posts content to Mastodon.
    Args:
        mastodon (Mastodon): The Mastodon instance to use.
        interval (int): The interval in seconds between posting content.
        
    Returns:
        None

    ToDo:
        - Move text patterns to settings.json
    '''

    # Path where the media files are stored
    path = "content/images/"
    
    # Create the directory if it doesn't exist
    if not os.path.exists(path):
        os.makedirs(path)
    
    # Create the last posted file if it doesn't exist
    if not os.path.exists("content/lastPosted.txt"):
        with open("content/lastPosted.txt", 'w') as file:
            file.write("0")

    # Read the last posted number from the file
    last_posted = config['lastPosetd']
    
    # Get the list of all filenames in the directory and sort them
    all_files = sorted(os.listdir(path), key=lambda x: int(x.split('.')[0]))
    
    # Find the index of the last posted file, if it exists
    last_index = next((i for i, filename in enumerate(all_files) if filename.startswith(str(last_posted))), -1)

    # Iterate through the files starting from the last posted
    for filename in all_files[last_index + 1:]:
        # Extract just the number part of the filename
        file_num = int(filename.split('.')[0])
        media_path = os.path.join(path, filename)

        try:
            # Prepare the alt text and metadata for posting
            alt_text = "#Cat" + str(file_num)
            metadata = mastodon.media_post(media_path, "image/jpg", description=alt_text)
            
            # Construct the toot text and post it
            toot_text = "#CatsOfMastodon\n" + alt_text + "\n\n"
            #mastodon.status_post(toot_text, media_ids=metadata["id"], visibility="public")
            
            # Update the last posted number
            last_posted = file_num

            print(f"Posted: {file_num}")
            time.sleep(interval)  # Respect the rate limits
            
        except MastodonInternalServerError as errorcode:
            logging.error(f"MastodonInternalServerError: {errorcode}")

# Thread worker
async def worker(mastodon, postContentbool, interval, loop):
    '''This function starts the taska that will listens to the stream
    Args:
        mastodon (Mastodon): The Mastodon instance to use.
        postContentbool (int): Whether to post content or not.
        interval (int): The interval in seconds between posting content.
        loop (asyncio.AbstractEventLoop): The event loop to use.
    
    Returns:
        None

    ToDo: 
            - Add a way to stop the taska
            - Add a way to restart the tasks


    '''

    # Start the worker
    logging.info('Starting streaming...')

    # Content tooting
    if postContentbool == 1:
        await toot_content(mastodon, interval)

    # Hashtag listening
    # Create a listener for each hashtag
    # The listener will be called when a new status arrives
    async def start_stream(hashtag):
        # Check if the stream is healthy
        try:
            healthy = mastodon.stream_healthy()
            if healthy == True:
                listener = HashtagListener(mastodon, loop)
                await loop.run_in_executor(None, mastodon.stream_hashtag, hashtag, listener, 0, 1, 300, 1, 5)
        except Exception as e:
            logging.error(f"Error starting streaming task: {e}")

    tasks = [start_stream(hashtag) for hashtag in hashtags]
    await asyncio.gather(*tasks)

# Get settings
async def get_settings():
    async with aiofiles.open('components/settings.html', 'r', encoding='utf-8') as file:
        settings_template = await file.read()
    config = load_config()
    return await render_template_string(settings_template, configuration=config)

# Get worker status
async def get_worker_status():
    ''' Placeholder for worker status'''
    async with aiofiles.open('components/worker.html', 'r', encoding='utf-8') as file:
        worker = await file.read()
    return worker

# Render Account Information
async def get_account():
    html = f'<div class="userAvatar"><img src="{user.avatar}" alt="{user.username}" /></div>'
    return html

# Broadcast message
async def broadcast_message(message):
    for connection in connections:
        try:
            await connection.send(message)
        except Exception as e:
            print(f"Error sending message: {e}")

# Route for the index page
@app.route('/')
async def index():

    # Get Account Information
    accountInfo = await get_account()

    # Settings
    settings = await get_settings()

    # Gwt Worker Status
    workerStatus = await get_worker_status()

    return await render_template('index.html',
        accountInfo=accountInfo,
        settings=settings,
        workerStatus=workerStatus,
    )

# Submit settings
@app.route('/submit_settings', methods=['POST'])
async def submit_settings():

    # Use await with request.form to get the form data asynchronously
    form_data = await request.form

    # Correctly use getlist to handle multiple values for each field
    hashtags = form_data.getlist('Hashtags[]')
    print(hashtags)
    bad_words = form_data.getlist('bad_words[]')
    bad_hashtags = form_data.getlist('bad_hashtags[]')
    bad_accounts = form_data.getlist('bad_accounts[]')

    new_data_dict = {
        'hashtags': hashtags,
        'bad_words': bad_words,
        'bad_hashtags': bad_hashtags,
        'bad_accounts': bad_accounts,
    }

    print(new_data_dict)

    # Add every other key
    for key in form_data:
        if key not in new_data_dict and not key.endswith('[]'):
            new_data_dict[key] = form_data.get(key)

    # Update the configuration with new data
    update_config(config, new_data_dict)

    return await index()
    
# WebSocket route
@app.websocket("/ws")
async def ws():
    connections.add(websocket._get_current_object())
    try:
        while True:
            # Receive a message from the client
            message = await websocket.receive()
            await broadcast_message(message)
    except:
        # Handle exceptions, e.g., client disconnecting
        await broadcast_message("Client disconnected.")
        pass
    finally:
        connections.remove(websocket._get_current_object())

# Initialize the main function
async def main():
    # Check for secrets
    check_for_secrets()  # Ensure this function sets necessary secrets

    # Initialize Mastodon
    mastodon = Mastodon(access_token = 'usercred.secret')

    global user
    user = mastodon.me()

    # Who Am I
    logging.info(user.username)

    # Start thread worker
    try:
        # Get event loop and run the quart app
        loop = asyncio.get_event_loop()
        # Start the worker
        await worker(mastodon, postContent, interval, loop)
        # Run the Quart app
        await app.run_task()
    except KeyboardInterrupt:
        logging.error("Stopping worker...")
    except Exception as errorcode:
        logging.error("ERROR: " + str(errorcode))
    
if __name__ == "__main__":
    asyncio.run(main())