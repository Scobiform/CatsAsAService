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

# Localization
localization = {}

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

# Load the localization from the localization.json file
def load_localization():
    try:
        with open('localization.json', 'r', encoding='utf-8') as localization_file:
            localization = json.load(localization_file)
            print("Localization loaded successfully.")
            return localization
    except FileNotFoundError:
        print("localization.json file not found.")
    except json.JSONDecodeError as e:
        print(f"An error occurred while decoding localization.json: {e}")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
    return {}

# Load the localization
localization = load_localization()

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

# Streaming manager
streaming_manager = None

# Is the stream running
stream_running = config['stream_running']

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

# Content tooting
# ToDo: Encapsulate this function in a class and get the text patterns from settings
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

# Hashtag Listener
class HashtagListener(StreamListener):
    '''A listener for streaming hashtag updates.
    Args:
        mastodon_instance (Mastodon): The Mastodon instance to use.
        loop (asyncio.AbstractEventLoop): The event loop to use.
        
    #ToDo: Keep track of the last status ID to avoid reboosting the same status

    '''
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

# Streaming Manager
class StreamingManager:
    """A manager for starting and stopping streaming tasks for hashtags.

    Args:
        mastodon (Mastodon): The Mastodon instance to use.
        loop (asyncio.AbstractEventLoop): The event loop to use.
        tasks (list): The list of streaming tasks to manage.
        hashtags (list): The list of hashtags to stream.
    
    """

    def __init__(self, mastodon, loop):
        self.mastodon = mastodon
        self.loop = loop
        self.tasks = tasks
        self.hashtags = hashtags

    async def start_stream(self, hashtag, max_retries=7, retry_delay=42):
        """Attempt to start streaming for a hashtag with retries.

        Args:
            hashtag (str): The hashtag to stream.
            max_retries (int): Maximum number of retry attempts.
            retry_delay (int): Delay between retries in seconds.
        """
        attempt = 0
        while attempt < max_retries:
            try:
                healthy = self.mastodon.stream_healthy()
                if healthy:
                    listener = HashtagListener(self.mastodon, self.loop)
                    await self.loop.run_in_executor(None, self.mastodon.stream_hashtag, hashtag, listener, 0, 1, 300, 1, 5)
                    message = f"Successfully started streaming for #{hashtag} <br>"
                    logging.info(message)
                    await broadcast_message(message)
                    break  # Streaming started successfully, exit the loop
                else:
                    logging.warning(f"Streaming not healthy for #{hashtag}, will retry...")
                    await broadcast_message(f"Streaming not healthy for #{hashtag}, will retry...")
            except Exception as e:
                logging.error(f"Error starting streaming task for #{hashtag}: {e}")
            
            attempt += 1
            if attempt < max_retries:
                await asyncio.sleep(retry_delay)  # Wait before retrying
            else:
                logging.error(f"Failed to start streaming for #{hashtag} after {max_retries} attempts")

    async def start(self):
        """Start all streaming tasks."""
        logging.info('Starting streaming...')
        await broadcast_message("Starting streaming. Give it some time to start all listeners...")
        for hashtag in self.hashtags:
            task = asyncio.create_task(self.start_stream(hashtag, 7, 42))
            self.tasks.append(task)
        await asyncio.gather(*self.tasks)

    async def stop(self):
        """Stop all streaming tasks."""
        await broadcast_message("Stopping all streaming tasks...")
        for task in self.tasks:
            task.cancel()
        # Wait for all tasks to be cancelled, ignoring cancellation exceptions
        await asyncio.gather(*self.tasks, return_exceptions=True)
        self.tasks = []  # Reset tasks list

# Get settings
async def get_settings():
    async with aiofiles.open('components/settings.html', 'r', encoding='utf-8') as file:
        settings_template = await file.read()
    config = load_config()
    return await render_template_string(settings_template, configuration=config, localization=localization)

# Get worker status
async def get_worker_status():
    ''' Get the worker component and render it with the current configuration.'''
    async with aiofiles.open('components/worker.html', 'r', encoding='utf-8') as file:
        worker = await file.read()
    return await render_template_string(worker, configuration=config)

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

    tasklist = tasks

    return await render_template('index.html',
        accountInfo=accountInfo,
        settings=settings,
        workerStatus=workerStatus,
        tasklist=tasklist
    )

# Submit settings
@app.route('/submit_settings', methods=['POST'])
async def submit_settings():
    '''Submit the settings form and update the configuration.
    
    #ToDo: Add auth to route
    '''
    # Use await with request.form to get the form data asynchronously
    form_data = await request.form

    # Correctly use getlist to handle multiple values for each field
    hashtags = form_data.getlist('Hashtags[]')
    bad_words = form_data.getlist('bad_words[]')
    bad_hashtags = form_data.getlist('bad_hashtags[]')
    bad_accounts = form_data.getlist('bad_accounts[]')

    new_data_dict = {
        'hashtags': hashtags,
        'bad_words': bad_words,
        'bad_hashtags': bad_hashtags,
        'bad_accounts': bad_accounts,
    }

    # Add every other key
    for key in form_data:
        if key not in new_data_dict and not key.endswith('[]'):
            new_data_dict[key] = form_data.get(key)

    # Update the configuration with new data
    update_config(config, new_data_dict)

    return await index()

# Start streaming
@app.route('/start_streaming', methods=['POST'])
async def start_streaming():
    '''Start the streaming manager.
    
    #ToDo: Add auth to route
    '''
    if streaming_manager:
        await streaming_manager.start()
        return jsonify({'status': 'streaming started'})
    return jsonify({'error': 'Streaming manager not initialized'}), 400

# Stop streaming
@app.route('/stop_streaming', methods=['POST'])
async def stop_streaming():
    '''Stop the streaming manager.

    #ToDo: Add auth to route
    '''
    if streaming_manager:
        await streaming_manager.stop()
        return jsonify({'status': 'streaming stopped'})
    return jsonify({'error': 'Streaming manager not initialized'}), 400

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
    logging.info('....' + user.username + ' successfully logged in.')


    # Content tooting
    #if postContent == '1':
    #    await toot_content(mastodon, interval)

    # Start tasks
    try:
        # Get event loop
        loop = asyncio.get_event_loop()

        # Start the streaming manager
        global streaming_manager
        streaming_manager = StreamingManager(mastodon, loop)

        # Run the Quart app
        await app.run_task()
    except KeyboardInterrupt:
        await streaming_manager.stop()
        logging.error("Stopping worker...")
    except Exception as errorcode:
        logging.error("ERROR: " + str(errorcode))
    
if __name__ == "__main__":
    asyncio.run(main())