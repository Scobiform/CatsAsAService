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
from quart import Quart, abort, render_template, send_from_directory, websocket, render_template_string, request, jsonify, redirect, url_for
from quart_auth import (
    AuthUser, current_user, login_required, login_user, logout_user, QuartAuth
)
from quart_bcrypt import Bcrypt
from mastodon import Mastodon
from mastodon.streaming import StreamListener, CallbackStreamListener
from mastodon.Mastodon import MastodonMalformedEventError, MastodonBadGatewayError, MastodonServiceUnavailableError, MastodonNetworkError, MastodonAPIError, MastodonInternalServerError, MastodonIllegalArgumentError

# CatsAsAService (CaaS)
# AGPLv3 License

# The web interface will allow you to monitor messages from mastodon and the bot, 
# start and stop the bot, change settings, and organize the content archive.
# http://localhost:5000

# THIS IS ONLY FOR DEVELOPMENT

# Requirements:
# Mastodon.py (pip install Mastodon.py) - MIT License - https://github.com/halcy/Mastodon.py
# Mastodon.py documentation: https://mastodonpy.readthedocs.io/en/stable/
# Quart (pip install Quart) - BSD License - https://github.com/pallets/Quart
# Quart documentation: https://Quart.palletsprojects.com/en/3.0.x/

# Configuration
config = {}

# Localization
localization = {}

# Users
users = {}

# Setting up threads
tasks = [] # List of threads we will start

# Load the configuration from the settings.json file
def load_config():
    try:
        with open('config/settings.json', 'r', encoding='utf-8') as config_file:
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
        with open('config/localization.json', 'r', encoding='utf-8') as localization_file:
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

# Load the users from the users.json file
# Load users from JSON file
with open('config/users.json') as f:
    user_data = json.load(f)
    users = user_data['users']
    print(users)

# Mastodon configuration
app_name = config['app_name']
instance_url = config['instance_url']
email = config['mastodon_email']
password = config['mastodon_password']

# UI configuration
heartbeatIcon = config['heartbeatIcon']

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

# Content manager
content_manager = None

# Is the stream running
global stream_running
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
    with open('config/settings.json', 'w', encoding='utf-8') as config_file:
        json.dump(configuraion, config_file, indent=4)

# Update one key value in the settings.json file
async def update_settings(key, value):
    settings_file = 'config/settings.json'
    try:
        # Attempt to read the current settings
        async with aiofiles.open(settings_file, mode='r', encoding='utf-8') as file:
            settings = json.loads(await file.read())
        
        # Update the specific key-value pair
        settings[key] = value
        
        # Write the updated settings back to the file
        async with aiofiles.open(settings_file, mode='w', encoding='utf-8') as file:
            await file.write(json.dumps(settings, indent=4))

    except FileNotFoundError:
        logging.error("settings.json file does not exist.")
    except Exception as e:
        logging.error(f"Failed to update settings: {e}")

# Get or Create app.seccret with a unique app.secret_key
# return only the string
def get_or_create_app_secret():
    if os.path.exists('app.secret'):
        with open('app.secret', 'r') as file:
            return file.read()
    else:
        secret_key = generate_secret_key()
        print(secret_key)
        with open('app.secret', 'w', encoding='utf-8') as file:
            file.write(secret_key)
        return secret_key
    
# Generate unique secret key
def generate_secret_key():
    return os.urandom(24).hex()

# Create image folder
if not os.path.exists(config['content_path']):
    os.makedirs(config['content_path'])

# Quart app
app = Quart(__name__)
app.secret_key = get_or_create_app_secret() # app.secret_key
QuartAuth(app)
bcrypt = Bcrypt(app)
connections = set() # Websocket connections

# Hash password
def hash_password(password):
    return bcrypt.generate_password_hash(password).decode('utf-8')

# Check password
def check_password(hashed_password, password):
    return bcrypt.check_password_hash(hashed_password, password)

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
class ContentManager:
    '''A manager for posting content to Mastodon.
    
    Args:
        mastodon (Mastodon): The Mastodon instance to use.
        config (dict): Configuration settings, including interval and content path.
        loop (asyncio.BaseEventLoop): The event loop to run asynchronous tasks.
    
    '''
    def __init__(self, mastodon, config, loop):
        self.mastodon = mastodon
        self.config = config
        self.loop = loop
        self.task = None

    async def toot_content(self):
        '''Post content to Mastodon with a specified interval.'''
        try:
            # Get the list of all filenames in the directory
            all_files = sorted(os.listdir(self.config['content_path']))

            # Determine the last posted filename
            last_posted = self.config.get('last_posted', None)
            if last_posted in all_files:
                last_index = all_files.index(last_posted)
                # Start with the next file after the last posted one, or at the beginning if it was the last
                all_files = all_files[last_index+1:] + all_files[:last_index+1]
            else:
                # If the last posted file is not in the directory, start from the beginning
                self.config['last_posted'] = all_files[-1]  # Assume the last one was posted

            while True:  # Continuously loop through the files
                for filename in all_files:
                    media_path = os.path.join(self.config['content_path'], filename)
                    #print(media_path)

                    if self.config['status_post'] == 'True':
                        # Upload the media
                        alt_text = self.config['tootAltTextPattern']
                        metadata = self.mastodon.media_post(media_path, "image/jpg", description=alt_text)
                        
                        # Toot the content
                        toot_text = self.config['tootPattern']
                        self.mastodon.status_post(toot_text, media_ids=[metadata['id']], visibility="public")

                    message = f"<img src='{media_path}' alt='{filename}' />"
                    await broadcast_message(message)
                    
                    # Save the last posted filename
                    self.config['last_posted'] = filename
                    await update_settings('last_posted', filename)

                    print(f"Posted: {filename}")
                    await asyncio.sleep(int(self.config['interval']))

                # After finishing the loop, start over from the beginning
                all_files = sorted(os.listdir(self.config['content_path']))

        except Exception as e:
            logging.error(f"Error posting content: {e} {type(e)}")

    async def start(self):
        '''Start the content manager.'''
        try:
            await broadcast_message("Starting content manager...")
            # Create task and run it
            self.task = asyncio.create_task(self.toot_content())
            await self.task

        except Exception as e:
            logging.error(f"Failed to start content manager: {e}")

    async def stop(self):
        '''Stop the content manager.'''
        await broadcast_message("Stopping content manager...")
        if self.task is not None:
            self.task.cancel()
            self.task = None

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
        self.config = config
        self.ä = None

    # Called when a new status arrives
    def on_update(self, status):

        if self.last_id == status.id:
            logging.info('....already boosted')
            return
        
        # Set the last ID
        self.last_id = status.id
        print(f"Status ID: {self.last_id}")

        # Log the status
        message = f"<br>{status.account.username} tooted: {status.content} <br>"
        asyncio.run_coroutine_threadsafe(broadcast_message(message), self.loop)

        # Skip counter - if it's 0, the status will be boosted
        skipCounter = 0  
        
        try:
            if status.account.username == self.mastodon.me().username:
                logging.info('....skipped')
            if status.account.username != self.mastodon.me().username:
                # Check if the account is a bot
                if config['isBot'] == 'True':
                    if status.account.bot == True:
                        logging.info('....bot - skipped')
                        skipCounter += 1
                # Check if there is media
                if config['hasMedia'] == 'True':
                    if len(status.media_attachments) == 0:
                        logging.info('no media - skipped')
                        skipCounter += 1   
                # Check if there is alt text
                if config['hasAltText'] == 'True':
                    for media in status.media_attachments:
                        # Skip if no Alt Text
                        if not media.description:
                            logging.info('....no alt text - skipped')
                            skipCounter += 1
                # Skip if too many hashtags
                if config['hasTooManyHashtags'] == 'True':
                    if len(status.tags) > 9:
                        logging.info('....too many hashtags - skipped')
                        skipCounter += 1
                # Check if there is a bad word
                if config['hasBadWord'] == 'True':
                    for word in bad_words:
                        if word in status.content:
                            logging.info('badword found - skipped')
                            skipCounter += 1
                # Check if there is a bad hashtag
                if config['hasBadHashtag'] == 'True':
                    for hashtag in bad_hashtags:
                        for tag in status.tags:
                            if hashtag == tag['name']:
                                logging.info('badhashtag found - skipped')
                                skipCounter += 1
                # Only boost if skipCounter is 0
                if skipCounter == 0:
                    if str(status.in_reply_to_account_id) == 'None':
                        if self.config['boost'] == 'True':
                            self.mastodon.status_reblog(status.id)
                            logging.info('....boosted')
                        if self.config['favorite'] == 'True':
                            self.mastodon.status_favourite(status.id)
                            logging.info('....favorited')
                        for media in status.media_attachments:
                            if media.type == "image":
                                message = f"<a href='{status.url}' target='_blank'><img src='{media.url}' alt='{media.description}' /></a>"
                                asyncio.run_coroutine_threadsafe(broadcast_message(message), self.loop)
                                logging.info('....image boosted')
                            if media.type == "video":
                                message = f"<video src='{media.url}' controls />"
                                asyncio.run_coroutine_threadsafe(broadcast_message(message), self.loop)
                                logging.info('....video boosted')
            # Output score and set skipCounter to 0
            asyncio.run_coroutine_threadsafe(broadcast_message('Score: ' + str(skipCounter)), self.loop)
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
    return await render_template_string(settings_template, configuration=config, localization=localization)

# Get worker status
async def get_worker_status():
    ''' Get the worker component and render it with the current configuration.'''
    async with aiofiles.open('components/worker.html', 'r', encoding='utf-8') as file:
        worker = await file.read()
    return await render_template_string(worker, configuration=config)

# Get login component
async def get_login():
    ''' Get the login component.'''
    async with aiofiles.open('components/login.html', 'r', encoding='utf-8') as file:
        login = await file.read()
    return await render_template_string(login)

# Render Account Information
async def get_account():
    html = f'<div class="userAvatar"><img src="{user.avatar}" alt="{user.username}" /></div>'
    return html

# Get trending hashtags
async def get_trending_hashtags():
    trending_hashtags = mastodon.trending_tags()
    return trending_hashtags

# Get media from content_path
async def get_media():
    ''' Get the media files from the content_path and return them as components.
    
    Returns:
        list: A list of media files.
    '''
    media = []
    for file in os.listdir(config['content_path']):
        if file.endswith('.jpg') or file.endswith('.png') or file.endswith('.gif') or file.endswith('.mp4'):
            media.append(file)
    return media

# Get any file as a component
async def get_any_file_as_component(file):
    ''' Get the content of a file and return it as a component.'''
    async with aiofiles.open(file, 'r', encoding='utf-8') as file:
        component = await file.read()
    return component

# Broadcast message
async def broadcast_message(message):
    for connection in connections:
        try:
            await connection.send(message)
        except Exception as e:
            print(f"Error sending message: {e}")

# Login route
@app.route('/login', methods=['POST'])
async def login():
    form_data = await request.form
    username = form_data.get('username')
    password = form_data.get('password')

    logging.info("Login attempt for user: %s", username)

    hashed_password = users.get(username)
    if hashed_password and check_password(hashed_password, password):
        user = AuthUser(username)
        login_user(user)
        return redirect(url_for('index'))
    else:
        return 'Login Failed', 401

# Logout route
@app.route('/logout', methods=['POST'])
async def logout():
    logout_user()
    return redirect(url_for('index'))

# Route for the index page
@app.route('/')
async def index():
    # Get Account Information
    accountInfo = await get_account()

    # Settings
    settings = await get_settings()

    # Gwt Worker Status
    workerStatus = await get_worker_status()

    # Get app logo
    logo = await get_any_file_as_component('components/logo.svg')

    # Get media
    media_list = await get_media()

    # Get login component
    login = await get_login()

    return await render_template('index.html',
        accountInfo=accountInfo,
        settings=settings,
        workerStatus=workerStatus,
        logo=logo,
        media_list=media_list,
        login=login
    )

# Submit settings
@app.route('/submit_settings', methods=['POST'])
@login_required
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
@login_required
async def start_streaming():
    '''Start the streaming manager.
    
    #ToDo: Add auth to route

    '''
    if streaming_manager:
        # Update the stream_running status
        try:
            stream_running = 'running'
            await update_settings('stream_running', stream_running)
            load_config()
            print('Streaming: ' + config['stream_running'])
        except Exception as e:
            logging.error(f"Failed to update stream_running status: {e}")
        await streaming_manager.start()
        return jsonify({'status': 'streaming started'})
    return jsonify({'error': 'Streaming manager not initialized'}), 400

# Stop streaming
@app.route('/stop_streaming', methods=['POST'])
@login_required
async def stop_streaming():
    '''Stop the streaming manager.

    #ToDo: Add auth to route
    '''
    if streaming_manager:
        # Update the stream_running status
        try:
            stream_running = 'stopped'
            await update_settings('stream_running', stream_running)
            load_config()
            print('Streaming: ' + config['stream_running'])
        except Exception as e:
            logging.error(f"Failed to update stream_running status: {e}")
        await streaming_manager.stop()
        return jsonify({'status': 'streaming stopped'})
    return jsonify({'error': 'Streaming manager not initialized'}), 400

# Start content manager
@app.route('/start_content', methods=['POST'])
@login_required
async def start_content():
    '''Start the content manager.'''
    if content_manager:
        load_config()
        await update_settings('postContent', 'True')
        await content_manager.start()
        return jsonify({'status': 'content started'})
    return jsonify({'error': 'Content manager not initialized'}), 400

# Stop content manager
@app.route('/stop_content', methods=['POST'])
@login_required
async def stop_content():
    '''Stop the content manager.'''
    if content_manager:
        load_config()
        await update_settings('postContent', 'False')
        await content_manager.stop()
        return jsonify({'status': 'content stopped'})
    return jsonify({'error': 'Content manager not initialized'}), 400

# Serve images
@app.route('/content/images/<path:filename>')
@login_required
async def serve_image(filename):
    """Serve files from the content/images/ directory."""
    if ".." in filename or filename.startswith("/"):
        # Basic security check to prevent accessing files outside the directory
        abort(404)
    
    full_path = os.path.join(config['content_path'], filename)
    if not os.path.isfile(full_path):
        # If the file does not exist, return a 404 error
        abort(404)

    return await send_from_directory(config['content_path'], filename)

# Get instance information
@app.route('/instance')
@login_required
async def get_instance():
    ''' Get the instance information.'''
    instance = mastodon.instance()
    return jsonify(instance)

# Get node information
@app.route('/nodeinfo')
@login_required
async def get_node():
    ''' Get the node information.'''
    node = mastodon.instance_nodeinfo()
    return jsonify(node)

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
    global mastodon
    mastodon = Mastodon(access_token = 'usercred.secret')

    # Hash password
    #hashed_password = hash_password('youcanloginnow')
    #print(hashed_password)

    global user
    user = mastodon.me()

    # Who Am I
    logging.info('....' + user.username + ' successfully logged in.')

    # Get event loop
    loop = asyncio.get_event_loop()

    # Start the streaming manager
    global streaming_manager
    streaming_manager = StreamingManager(mastodon, loop)

    # Start the content manager
    global content_manager
    content_manager = ContentManager(mastodon, config, loop)

    # Run the Quart app
    await app.run_task()

if __name__ == "__main__":
    asyncio.run(main())