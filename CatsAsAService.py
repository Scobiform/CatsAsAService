import os
import threading
import time
import logging
import datetime
import asyncio
import aiofiles
from threading import Thread
from datetime import date
from concurrent.futures import ThreadPoolExecutor
from quart import Quart, render_template, websocket
from mastodon import Mastodon
from mastodon.streaming import StreamListener, CallbackStreamListener
from mastodon.Mastodon import MastodonMalformedEventError, MastodonBadGatewayError, MastodonServiceUnavailableError, MastodonNetworkError, MastodonAPIError, MastodonInternalServerError, MastodonIllegalArgumentError

# CatsAsAService (CaaS)
# AGPLv3 License

# The web interface will allow you to monitor messages from mastodon and the bot, 
# start and stop the bot, view logs, change settings, and organize the content archive
# http://localhost:5000

# Requirements:
# Mastodon.py (pip install Mastodon.py) - MIT License - https://github.com/halcy/Mastodon.py
# Mastodon.py documentation: https://mastodonpy.readthedocs.io/en/stable/
# Quart (pip install Quart) - BSD License - https://github.com/pallets/Quart
# Quart documentation: https://Quart.palletsprojects.com/en/3.0.x/

# Configuration
# You can remove your credentials after the first run
app_name = 'CaaS - CatsAsAService'  # Replace with your desired app name
instance_url = 'mastodon.social'  # Replace with your Mastodon instance URL
email = ''  # Replace with your Mastodon account email
password = ""  # Replace with your Mastodon account password

# UI configuration
heartbeatIcon = "😻"

# Bot Settings
workerStatus = 0 # 0 = Stopped, 1 = Running
cancel_token = threading.Event() # Cancellation flag for the worker threads

# Configure logging
logging.basicConfig(
    filename='CaaS.log',
    filemode='a',  # Append to the log file, don't overwrite
    format='%(asctime)s - %(levelname)s - %(message)s',
    level=logging.INFO)

# Hashtags to listen to
hashtags = [
            'CatsOfMastodon',
            'Caturday',
            'CatsOfTheFediverse',
            'FediCats',
            'Cats',
            'CatContent',
            "BlackCatsMatter",
            'サイベリアン',
            '猫',
            "МАНУЛ"
]

# bad words
bad_words = [
    'elon musk',
]

# bad hashtags
bad_hashtags = [
    'badhashtag',
]

# bad accounts
bad_accounts = [
    'UnitedSpaceCats',
]

# Post content (0 = no, 1 = yes)
postContent = 0

# Interval in seconds for the sleep period between posting content
interval = 18243

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

    # Called when a new status arrives
    def on_update(self, status):

        # Broadcast status
        #asyncio.run_coroutine_threadsafe(broadcast_message(status.content), self.loop)

        # Log status
        logging.info('New status arrived')
        logging.info('....' + status.account.username)

        # Skip counter - if it's 0, the status will be boosted
        skipCounter = 0  
        
        try:
            if status.account.username == self.mastodon.me().username:
                logging.info('....skipped')
            if status.account.username != self.mastodon.me().username:
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
                    # for word in badWords:
                    #     if word in status.content:
                    #         logging.info('badword found - skipped')
                    #         skipCounter += 1
                    # # Check if there is a bad hashtag
                    # for hashtag in badHashtags:
                    #     for tag in status.tags:
                    #         if hashtag == tag['name']:
                    #             logging.info('badhashtag found - skipped')
                    #             skipCounter += 1
                    # Only boost if skipCounter is 0
                    if skipCounter == 0:
                        if str(status.in_reply_to_account_id) == 'None':
                            #self.mastodon.status_reblog(status.id)
                            #self.mastodon.status_favourite(status.id)
                            for media in status.media_attachments:
                                if media.type == "image":
                                    message = f"<a href='{status.url}' target='_blank'><img src='{media.url}' alt='{media.description}' /></a>"
                                if media.type == "video":
                                    message = f"<video src='{media.url}' controls />"
                            {status.media_attachments[0].url}
                            asyncio.run_coroutine_threadsafe(broadcast_message(message), self.loop)
                            logging.info('....boosted')
                else:
                    asyncio.run_coroutine_threadsafe(broadcast_message('Bot...'), self.loop)
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
            message = heartbeatIcon
            #asyncio.run_coroutine_threadsafe(broadcastMessage(message), self.loop)
        except Exception as errorcode:
            logging.error("ERROR: " + str(errorcode))
            return
        return
    
    # Called when a notification arrives
    def on_notification(self, notification):
        try:
            message = notification.type
            asyncio.run_coroutine_threadsafe(broadcast_message(message), self.loop)
        except Exception as errorcode:
            logging.error("ERROR: " + str(errorcode))
            return
        return
    
    # Called when a delete event arrives
    def on_delete(self, status):
        try:
            message = "Deleted: " + status.id
            asyncio.run_coroutine_threadsafe(broadcast_message(message), self.loop)
        except Exception as errorcode:
            logging.error("ERROR: " + str(errorcode))
            return
        return
    
    # Called when a error event arrives
    def on_error(self, error):
        try:
            message = "Error: " + error
            asyncio.run_coroutine_threadsafe(broadcast_message(message), self.loop)
        except Exception as errorcode:
            logging.error("ERROR: " + str(errorcode))
            return
        return
    
    # Called when a unknown event arrives
    def on_unknown_event(self, unknown_event):
        try:
            message = "Unknown Event: " + unknown_event
            asyncio.run_coroutine_threadsafe(broadcast_message(message), self.loop)
        except Exception as errorcode:
            logging.error("ERROR: " + str(errorcode))
            return
        return
    
    # Called when a conversation event arrives
    def on_conversation(self, conversation):
        try:
            message = "Conversation: " + conversation
            asyncio.run_coroutine_threadsafe(broadcast_message(message), self.loop)
        except Exception as errorcode:
            logging.error("ERROR: " + str(errorcode))
            return
        return

# Content tooting
async def toot_content(mastodon, interval):

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
    with open("content/lastPosted.txt", 'r') as file:
        last_posted_str = file.readline().strip()
        last_posted = int(last_posted_str) if last_posted_str.isdigit() else 0
    print("Current startNumber: " + str(last_posted))
    
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
            mastodon.status_post(toot_text, media_ids=metadata["id"], visibility="public")
            
            # Update the last posted number
            with open("content/lastPosted.txt", 'w') as file:
                file.write(str(file_num))

            print(f"Posted: {file_num}")
            time.sleep(interval)  # Respect the rate limits
            
        except MastodonInternalServerError as errorcode:
            logging.error(f"MastodonInternalServerError: {errorcode}")

# Thread worker
async def worker(mastodon, postContentbool, interval, loop):
    '''This function starts the worker thread that listens to the stream and posts content.
    Args:
        mastodon (Mastodon): The Mastodon instance to use.
        postContentbool (int): Whether to post content or not.
        interval (int): The interval in seconds between posting content.
        loop (asyncio.AbstractEventLoop): The event loop to use.
    
    Returns:
        None

    ToDo: 
            - Add cancellation token to stop the worker threads.
            - Add a way to restart the worker threads.

    '''

    # Setting up threads
    threads = [] # List of threads we will start

    # Start the worker
    logging.info('Starting thread worker...')

    # Check if the stream is healthy
    try:
        healthy = mastodon.stream_healthy()
        logging.info(f"Stream healthy: {healthy}")
    except Exception as e:
        logging.error(f"Error checking stream health: {e}")
        return

    # Content tooting
    if postContentbool == 1:
        await toot_content(mastodon, interval)

    # Hashtag listening
    # Create a listener for each hashtag
    # The listener will be called when a new status arrives
    for hashtag in hashtags:
        listener = HashtagListener(mastodon, loop)
        stream = Thread(target=mastodon.stream_hashtag, args=[hashtag, listener, 0, 1, 300, 1, 300])
        threads.append(stream)

    # Start all threads
    for thread in threads:
        thread.daemon = True
        thread.start()

    for thread in threads:
        thread.join()

# Get log file
async def get_log():
    async with aiofiles.open('CaaS.log', 'r') as file:
        log = await file.read()
    return log

# Clean log file
async def clean_log():
    await broadcast_message("Cleaning log...")
    with open('CaaS.log', 'w') as file:
        file.write("")
    await broadcast_message("Cleaned log.")

# Get settings
async def get_settings():
    ''' Placeholder for settings'''
    async with aiofiles.open('components/settings.html', 'r', encoding='utf-8') as file:
        settings = await file.read()
    return settings

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

    # Get Log
    log = await get_log()

    # Settings
    settings = await get_settings()

    # Gwt Worker Status
    workerStatus = await get_worker_status()

    return await render_template('index.html',
        accountInfo=accountInfo,
        log=log,
        settings=settings,
        workerStatus=workerStatus
    )

# Api route
app.route("/api")
async def json():
    return {"hello": "world"}

# WebSocket route
@app.websocket("/ws")
async def ws():
    connections.add(websocket._get_current_object())
    try:
        while True:
            # Receive a message from the client
            message = await websocket.receive()
            print(f"{message}")
    except:
        # Handle exceptions, e.g., client disconnecting
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