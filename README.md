# Nextcloud Deck to Discord Bot

## About
This bot was developed to bridge Nextcloud Deck boards with Discord channels, enabling regular task tracking and collaboration. 
Built for [Unsprawling Calgary](https://community.unsprawling.org/).

*Disclaimer: This software was generated through AI assistance. While efforts have been made to ensure reliability and security, users should perform their own security audits before deploying in production environments.*

## Features
- Regular timed monitoring of Nextcloud Deck boards
- Automatic Discord posts for Deck updates
- Display of cards with:
  - Due dates
  - Assigned users
  - Labels
  - Card descriptions
- Secure credential management
- Docker containerization
- Robust error handling and logging
- Automatic reconnection and retry logic

## Prerequisites
- Docker and Docker Compose
- Nextcloud instance with Deck app installed
- Discord webhook URL
- Python 3.11+ (if running without Docker)

## Installation

### Using Docker (Recommended)
1. Clone the repository:
```bash
git clone https://github.com/your-repo/nextcloud-deck-discord-bot
cd nextcloud-deck-discord-bot
```

2. Create a `.env` file with your credentials:
```env
NEXTCLOUD_URL=https://your-nextcloud-url
NEXTCLOUD_USERNAME=your-username
NEXTCLOUD_PASSWORD=your-password
DISCORD_WEBHOOK_URL=your-webhook-url
BOARD_ID=your-board-number
CHECK_INTERVAL=60
```

3. Build and run using Docker Compose:
```bash
docker-compose up -d
```

### Manual Installation
1. Clone the repository
2. Install requirements:
```bash
pip install -r requirements.txt
```
3. Set environment variables
4. Run the bot:
```bash
python deck_bot.py
```

## Configuration
The bot can be configured using the following environment variables:

| Variable | Description | Required | Default |
|----------|-------------|----------|---------|
| NEXTCLOUD_URL | Your Nextcloud instance URL | Yes | - |
| NEXTCLOUD_USERNAME | Nextcloud username | Yes | - |
| NEXTCLOUD_PASSWORD | Nextcloud password | Yes | - |
| DISCORD_WEBHOOK_URL | Discord webhook URL | Yes | - |
| BOARD_ID | Nextcloud Deck board ID | Yes | - |
| CHECK_INTERVAL | Update check interval in seconds | No | 60 |

## Security Considerations
- Credentials are handled via environment variables
- Implements retry logic with exponential backoff
- Uses secure HTTPS connections
- Includes error handling and logging
- Docker container runs with minimal privileges

## Troubleshooting
Common issues and solutions:

1. Connection errors:
   - Verify Nextcloud URL is accessible
   - Check credentials
   - Ensure webhook URL is valid

2. Missing updates:
   - Verify board ID is correct
   - Check CHECK_INTERVAL setting
   - Review logs for errors

## Logs
Logs are available through Docker:
```bash
docker logs deck-discord-bot
```

## Contributing
Contributions are welcome, please note that any modifications should be thoroughly tested and reviewed.

## License
GPLv3 License - See LICENSE file for details

## Acknowledgments
- Created by Corbin with Claude 3.5 Sonnet (Anthropic)
- Developed for Unsprawling Calgary
- Uses Nextcloud Deck API
- Built with [Discord Webhook](https://github.com/lovvskillz/python-discord-webhook) by lovvskillz

## Support
For issues and support:
1. Check the troubleshooting guide
2. Review Docker logs
3. Open an issue on GitHub
4. Contact Unsprawling Calgary team

---

*Note: This bot was created using AI assistance. While it has been designed with security and reliability in mind, users should perform their own security assessment before deployment in production environments.*
