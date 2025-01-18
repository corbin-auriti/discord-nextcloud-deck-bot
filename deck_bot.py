# deck_bot.py
import os
import requests
import json
import time
from discord_webhook import DiscordWebhook, DiscordEmbed
from datetime import datetime
import logging
from typing import Optional, List, Dict, Any
from urllib3.util import Retry
from requests.adapters import HTTPAdapter

class DeckDiscordBot:
    def __init__(self):
        # Load configuration from environment variables
        self.nextcloud_url = os.getenv('NEXTCLOUD_URL')
        self.username = os.getenv('NEXTCLOUD_USERNAME')
        self.password = os.getenv('NEXTCLOUD_PASSWORD')
        self.webhook_url = os.getenv('DISCORD_WEBHOOK_URL')
        self.board_id = int(os.getenv('BOARD_ID', '0'))
        self.check_interval = int(os.getenv('CHECK_INTERVAL', '60'))

        if not all([self.nextcloud_url, self.username, self.password, 
                   self.webhook_url, self.board_id]):
            raise ValueError("Missing required environment variables")

        # Setup logging
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        self.logger = logging.getLogger(__name__)

        # Setup base URL and auth
        self.base_url = f"{self.nextcloud_url}/index.php/apps/deck/api/v1.0"
        self.auth = (self.username, self.password)
        self.headers = {
            'OCS-APIRequest': 'true',
            'Content-Type': 'application/json'
        }
        self.last_etag = None
        
        # Setup requests session with retry logic
        self.session = self._setup_requests_session()

    def _setup_requests_session(self) -> requests.Session:
        """Configure requests session with retry logic and timeouts"""
        session = requests.Session()
        retry_strategy = Retry(
            total=3,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504]
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        session.mount("http://", adapter)
        session.mount("https://", adapter)
        return session

    def _make_request(self, method: str, endpoint: str, **kwargs) -> Optional[Dict]:
        """Make HTTP request with error handling"""
        try:
            url = f"{self.base_url}/{endpoint}"
            response = self.session.request(
                method,
                url,
                headers=self.headers,
                auth=self.auth,
                timeout=10,
                **kwargs
            )
            response.raise_for_status()
            return response.json() if response.content else None
        except requests.exceptions.RequestException as e:
            self.logger.error(f"Request failed: {str(e)}")
            return None

    def get_board(self, board_id: int) -> Optional[Dict]:
        """Fetch board details safely"""
        return self._make_request('GET', f'boards/{board_id}')

    def get_stacks(self, board_id: int) -> Optional[List[Dict]]:
        """Fetch all stacks for a board safely"""
        return self._make_request('GET', f'boards/{board_id}/stacks')

    def get_cards(self, board_id: int, stack_id: int) -> List[Dict]:
        """Fetch all cards for a stack safely"""
        response = self._make_request('GET', f'boards/{board_id}/stacks/{stack_id}')
        if response and 'cards' in response:
            return sorted(response['cards'], key=lambda x: x.get('order', 0))
        return []

    def create_card_description(self, card: Dict, number: int) -> str:
        """Create a formatted card description with number and metadata"""
        try:
            board_id = card.get('boardId') or self.board_id
            
            # Create card URL using the board ID from the current context
            card_url = f"{self.nextcloud_url}/apps/deck/#/board/{board_id}/card/{card['id']}"
            
            # Start with the numbered title and URL
            desc = f"{number}. [{card['title']}]({card_url})"
            
            # Add due date if exists and not null
            if card.get('duedate'):
                try:
                    due_date = datetime.fromisoformat(card['duedate'].replace('Z', '+00:00'))
                    desc += f"\n└ Due: {due_date.strftime('%Y-%m-%d')}"
                except ValueError:
                    self.logger.warning(f"Invalid date format for card {card['id']}")
            
            # Add assigned users if they exist
            if card.get('assignedUsers'):
                users = [f"@{user['participant']['displayname']}" 
                        for user in card['assignedUsers'] 
                        if 'participant' in user and 'displayname' in user['participant']]
                if users:
                    desc += f"\n└ Assigned: {', '.join(users)}"
            
            # Add labels if they exist
            if card.get('labels'):
                labels = [f"[{label['title']}]" for label in card['labels'] 
                         if 'title' in label]
                if labels:
                    desc += f"\n└ {' '.join(labels)}"
            
            return desc
        except Exception as e:
            self.logger.error(f"Error creating card description: {str(e)}")
            return f"{number}. [Error loading card]"

    def create_discord_message(self, board_data: Dict, stacks_data: List[Dict]) -> DiscordWebhook:
        """Create Discord embeds for each stack"""
        webhook = DiscordWebhook(url=self.webhook_url)
        
        # Add board title as main content
        webhook.content = f"**{board_data['title']}** - Updated {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        
        # Create an embed for each stack that has cards
        for stack in stacks_data:
            try:
                # Get and format cards
                cards = self.get_cards(board_data['id'], stack['id'])
                
                # Skip stacks with no cards
                if not cards:
                    continue
                    
                embed = DiscordEmbed(
                    title=stack['title'],
                    color='03b2f8'
                )
                
                card_descriptions = []
                for i, card in enumerate(cards, 1):
                    if 'boardId' not in card:
                        card['boardId'] = board_data['id']
                    card_desc = self.create_card_description(card, i)
                    card_descriptions.append(card_desc)
                
                if card_descriptions:
                    embed.description = '\n\n'.join(card_descriptions)
                    webhook.add_embed(embed)
            except Exception as e:
                self.logger.error(f"Error processing stack {stack.get('id')}: {str(e)}")
        
        return webhook

    def post_to_discord(self, webhook: DiscordWebhook) -> bool:
        """Post webhook to Discord channel safely"""
        try:
            response = webhook.execute()
            if response:
                self.logger.info("Successfully posted update to Discord")
                return True
            self.logger.error("Failed to post to Discord")
            return False
        except Exception as e:
            self.logger.error(f"Error posting to Discord: {str(e)}")
            return False

    def monitor_board(self):
        """Monitor board for changes and post updates to Discord"""
        self.logger.info(f"Starting monitoring of board {self.board_id}")
        
        while True:
            try:
                board = self.get_board(self.board_id)
                if not board:
                    self.logger.error("Failed to fetch board")
                    time.sleep(self.check_interval)
                    continue

                current_etag = board.get('ETag')
                
                if current_etag != self.last_etag:
                    self.logger.info(f"Board updated at {datetime.now()}")
                    
                    stacks = self.get_stacks(self.board_id)
                    if stacks:
                        webhook = self.create_discord_message(board, stacks)
                        if self.post_to_discord(webhook):
                            self.last_etag = current_etag
                else:
                    self.logger.debug(f"No updates found at {datetime.now()}")
                
            except Exception as e:
                self.logger.error(f"Error in monitor loop: {str(e)}")
            finally:
                time.sleep(self.check_interval)

if __name__ == "__main__":
    try:
        bot = DeckDiscordBot()
        bot.monitor_board()
    except Exception as e:
        logging.error(f"Fatal error: {str(e)}")

