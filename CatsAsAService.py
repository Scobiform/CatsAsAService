import os
import threading
import time
import logging
import datetime
from threading import Thread
from datetime import date
from concurrent.futures import ThreadPoolExecutor
from mastodon import Mastodon
from mastodon.streaming import StreamListener, CallbackStreamListener
from mastodon.Mastodon import MastodonMalformedEventError, MastodonBadGatewayError, MastodonServiceUnavailableError, MastodonNetworkError, MastodonAPIError, MastodonInternalServerError, MastodonIllegalArgumentError

# CatsAsAService (CaaS)
# GPLv3 License
# ucsf.scobiform.com

# This script will listen to given hashtags 
# After a hashtag is found, it will conditionally boost and favorite the status
# It also toots content from the catcontent folder
# Demo: https://mastodon.social/@UnitedSpaceCats

# Requirements:
# Mastodon.py (pip install Mastodon.py) - MIT License - https://github.com/halcy/Mastodon.py
# Mastodon.py documentation: https://mastodonpy.readthedocs.io/en/stable/ 

# Configure logging
logging.basicConfig(
    filename='CaaS.log',
    filemode='a',  # Append to the log file, don't overwrite
    format='%(asctime)s - %(levelname)s - %(message)s',
    level=logging.INFO)

# Hashtags to listen to
hashtags = [
            'CatsOfMastodon',
            'Caturday'
]

# bad words
badWords = [
            'shop',
            'buy', 
            'nft', 
            'coin', 
            'escort', 
            'xxx', 
            'Billionaire',
            'product',
            'sale',
            'discount',
            'download',
            'AI',
            'marketing',
            'seo',
        ]

# bad hashtags
badHashtags = [
            'nft',
            'coin',
            'xxx',
            'ai',
            'marketing',
            'seo',
            'shop',
            'buy',
            'sale',
            'discount',
            'download',
            'product',
            'AI',
        ]

# bad accounts
badAccounts = [
            'Billionaire',
            'Billionaires',
            'BillionaireMentor',
            'Billionaire_Bot',
            'Billionaire_Bot_',
]

# Create Mastodon App & User
def createSecrets():
    Mastodon.create_app(
        'UnitedSpaceCats',
        api_base_url = 'https://mastodon.social',
        to_file = 'clientcred.secret'
    )
    
    # Fill in your credentials - RUN ONCE
    '''
    mastodon = Mastodon(client_id = 'clientcred.secret',)
    mastodon.log_in(
        'your@mail.com',
        'password',
        to_file = 'usercred.secret'
    )
    '''

# Hashtag Listener
class HashtagListener(StreamListener):
    # Constructor
    def __init__(self, mastodon_instance):
        self.mastodon = mastodon_instance

    # Called when a new status arrives
    def on_update(self, status):

        logging.info('New status arrived')
        logging.info('....' + status.account.username)
        
        # Skip counter
        skipCounter = 0       
        
        try:
            if status.account.username == self.mastodon.me().username:
                logging.info('....skipped')
            if status.account.username != self.mastodon.me().username:
                if status.account.bot == False:
                    # Check if there is a bad account
                    for account in badAccounts:
                        if account == status.account.username:
                            logging.info('badaccount found - skipped')
                            skipCounter += 1
                    # Check if there is a bad word
                    for word in badWords:
                        if word in status.content:
                            logging.info('badword found - skipped')
                            skipCounter += 1
                    # Check if there is a bad hashtag
                    for hashtag in badHashtags:
                        for tag in status.tags:
                            if hashtag == tag['name']:
                                logging.info('badhashtag found - skipped')
                                skipCounter += 1
                    # Check if there is media
                    if len(status.media_attachments) == 0:
                        logging.info('no media - skipped')
                        skipCounter += 1
                    # Only boost if skipCounter is 0
                    if skipCounter == 0:
                        if str(status.in_reply_to_account_id) == 'None':
                            self.mastodon.status_reblog(status.id)
                            self.mastodon.status_favourite(status.id)
                            logging.info('....boosted')
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
        thread_name = threading.current_thread().name
        logging.info('. ' + thread_name)

# Content tooting
def tootContentArchive(mastodon, interval):

    # Path where the media files are stored
    path = "catcontent/cats/"
    
    # Create the directory if it doesn't exist
    if not os.path.exists(path):
        os.makedirs(path)
    
    # Create the last posted file if it doesn't exist
    if not os.path.exists("catcontent/lastPosted.txt"):
        with open("catcontent/lastPosted.txt", 'w') as file:
            file.write("0")

    # Read the last posted number from the file
    with open("catcontent/lastPosted.txt", 'r') as file:
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
            with open("catcontent/lastPosted.txt", 'w') as file:
                file.write(str(file_num))

            print(f"Posted: {file_num}")
            time.sleep(interval)  # Respect the rate limits
            
        except MastodonInternalServerError as errorcode:
            logging.error(f"MastodonInternalServerError: {errorcode}")

# Thread worker
def worker(mastodon, postContentbool, interval):

    # Check if the stream is healthy
    try:
        healthy = mastodon.stream_healthy()
        logging.info(f"Stream healthy: {healthy}")
    except Exception as e:
        logging.error(f"Error checking stream health: {e}")
        return

    # Setting up threads
    threads = [] # List of threads we will start

    # Start the worker
    logging.info('Starting thread worker...')

    # Content tooting
    if postContentbool == 1:
        contentArchive = Thread(target=tootContentArchive, args=[mastodon, interval])
        threads.append(contentArchive)

    # Hashtag listening
    # Create a listener for each hashtag
    # The listener will be called when a new status arrives
    for hashtag in hashtags:
        listener = HashtagListener(mastodon)
        stream = Thread(target=mastodon.stream_hashtag, args=[hashtag, listener, 0, 1, 300, 1, 300])
        threads.append(stream)

    # Start all threads
    for thread in threads:
        thread.daemon = True
        thread.start()

    for thread in threads:
        thread.join()

def main():
    # Interval in seconds for the sleep period between posting content
    interval = 18243

    mastodon = Mastodon(access_token = 'usercred.secret')

    # Who Am I
    logging.info(mastodon.me().username)

    # Settings
    postContentbool = 0

    # Start Worker
    try:
        worker(mastodon, postContentbool, interval)
    except KeyboardInterrupt:
        logging.error("Stopping worker...")
    except Exception as errorcode:
        logging.error("ERROR: " + str(errorcode))
    
if __name__ == "__main__":
    main()
input()