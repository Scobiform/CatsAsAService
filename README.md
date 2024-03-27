![CaaS](components/logo.svg)

# CatsAsAService (CaaS)

![GPLv3 License](https://img.shields.io/badge/license-GPLv3-blue.svg)
![Python version](https://img.shields.io/badge/python-3.x-blue.svg)

## Table of Contents

- [Introduction](#introduction)
- [Requirements](#requirements)
- [Setup](#setup)
- [Usage](#usage)
- [License](#license)

## Introduction

CatsAsAService is a bot for the Mastodon social network. 

**⚠️ Warning:** This bot is easily detectable by instance admins. Please do not use it for abuse or spam.

## Requirements

- Python 3.x (https://docs.python.org/3/license.html)
- Mastodon.py (`pip install Mastodon.py`) - MIT License - https://github.com/halcy/Mastodon.py
- [Mastodon.py Documentation](https://mastodonpy.readthedocs.io/en/stable/)
- Quart (pip install Quart) - BSD License - https://github.com/pallets/Quart
- Quart documentation: https://Quart.palletsprojects.com/en/3.0.x/
- Quart-Auth (pip install quart-auth) - MIT license - https://github.com/pgjones/quart-auth
- Quart-Auth documentation: https://quart-auth.readthedocs.io/en/latest/index.html
- Quart-Bcrypt (pip install quart-bcrypt) - https://github.com/Quart-Addons/quart-bcrypt
- Quart-Bcrypt documentation: https://quart-bcrypt.readthedocs.io/en/0.0.6/

## Setup

1. Clone the repository.
2. Install dependencies: `pip install -r requirements.txt`.

## Usage

- Set your Mastodon email and password once in the `settings.json` or via the web interface
- Run the script: `python3 CatsAsAService.py`.
- Use `Ctrl+C` to stop the script.

The web interface will allow you to monitor messages from mastodon and the bot, 
start and stop the bot, change settings, and organize the content archive
`http://localhost:5000`

## License

This project is licensed under the GPLv3 License - see the LICENSE file for details.
