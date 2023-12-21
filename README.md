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
CatsAsAService is a bot for the Mastodon social network. It boosts and favorites posts with specific hashtags and toots content from a designated folder. 

![Warning](https://img.shields.io/badge/warning-important-red.svg)

**⚠️ Warning:** This bot is easily detectable by instance admins. Please do not use it for abuse or spam.

## Requirements
- Python 3.x
- Mastodon.py (`pip install Mastodon.py`)
- [Mastodon.py Documentation](https://mastodonpy.readthedocs.io/en/stable/)

## Setup
1. Clone the repository.
2. Install dependencies: `pip install Mastodon.py`.
3. Create your `clientcred.secret` and `usercred.secret` by running `createSecrets()`.

## Usage
- Set your desired hashtags, bad words, and accounts in the script.
- Run the script: `python3 CatsAsAService.py`.
- Use `Ctrl+C` to stop the script.

## License
This project is licensed under the GPLv3 License - see the LICENSE file for details.
