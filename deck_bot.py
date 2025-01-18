import os
import requests
import json
import time
import re
from discord_webhook import DiscordWebhook, DiscordEmbed
from datetime import datetime
import logging
from typing import Optional, List, Dict, Any
from urllib3.util import Retry
from requests.adapters import HTTPAdapter
#from dotenv import load_dotenv


class DeckDiscordBot:
    
    DISCORD_EMBED_LIMIT = 4096

    def __init__(self):
        # Load configuration from environment variables
        self.nextcloud_url = os.getenv('NEXTCLOUD_URL')
        self.username = os.getenv('NEXTCLOUD_USERNAME')
        self.password = os.getenv('NEXTCLOUD_PASSWORD')
        self.webhook_url = os.getenv('DISCORD_WEBHOOK_URL')
        self.thread_id = os.getenv('DISCORD_THREAD_ID')
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
        """Fetch all stacks for a board safely, skip archived"""
        stacks = self._make_request('GET', f'boards/{board_id}/stacks')
        if stacks:
            # Filter out archived stacks
            return [stack for stack in stacks if not stack.get('archived', False)]
        return None

    def create_card_description(self, card: Dict, number: int) -> str:
        """Create a formatted card description with number and metadata"""
        try:
            board_id = card.get('boardId') or self.board_id
            
            # Create card URL using the board ID from the current context
            card_url = f"{self.nextcloud_url}/apps/deck/#/board/{board_id}/card/{card['id']}"
            
            # Start with the numbered title and URL
            desc = f"{number}. [{card['title']}]({card_url})"
            
            # Add first line of description if it exists
            if card.get('description'):
                first_line = re.sub(r'\*|~|\^|[^\s]\(.*?\)|\[.*?\]', '', card['description'].split('\n')[0].strip()) #Strip markdown
                if first_line:
                    desc += f"\n└ 🗒{first_line[:100]}..." if len(first_line) > 100 else f"\n└ 🗒{first_line}"
            
            # Add due date if exists and not null
            if card.get('duedate'):
                try:
                    due_date = datetime.fromisoformat(card['duedate'].replace('Z', '+00:00'))
                    desc += f"\n└ 📆***Due: {due_date.strftime('%Y-%m-%d')}***"
                except ValueError:
                    self.logger.warning(f"Invalid date format for card {card['id']}")
            
            # Add assigned users if they exist
            if card.get('assignedUsers'):
                users = [f"@{user['participant']['displayname']}" 
                        for user in card['assignedUsers'] 
                        if 'participant' in user and 'displayname' in user['participant']]
                if users:
                    desc += f"\n└ 👤Assigned: {', '.join(users)}"
            
            # Add labels if they exist
            if card.get('labels'):
                labels = [f"[{label['title']}]" for label in card['labels'] 
                         if 'title' in label]
                if labels:
                    desc += f"\n└ 🏷{' '.join(labels)}"
            
            return desc
        except Exception as e:
            self.logger.error(f"Error creating card description: {str(e)}")
            return f"{number}. [Error loading card]"

    def get_cards(self, board_id: int, stack_id: int) -> List[Dict]:
        """Fetch all cards for a stack safely"""
        response = self._make_request('GET', f'boards/{board_id}/stacks/{stack_id}')
        if response and 'cards' in response:
            # Filter out archived cards
            active_cards = [
                card for card in response['cards'] 
                if not card.get('archived', False)
            ]
            
            # Sort active cards
            cards = sorted(active_cards, key=lambda x: x.get('order', 0))
            
            # If no active cards, return empty list
            if not cards:
                return []        
            return cards

        return []


    def create_and_send_discord_messages(self, board_data: Dict, stacks_data: List[Dict]) -> None:
        """Create and send separate Discord embeds for each stack"""
        try:
            board_title = f"**{board_data['title']}** - {datetime.now().strftime('%B %d %Y - %H:%M')}"
            
            # Keep track of whether we've sent the first message
            first_message_sent = False
            
            # Process each stack separately
            for stack in stacks_data:
                try:
                    # Skip archived stacks
                    if stack.get('archived', False):
                        continue
                    
                    # Get and format cards
                    cards = self.get_cards(board_data['id'], stack['id'])
                    
                    # Skip stacks with no active cards
                    if not cards:
                        self.logger.debug(f"Skipping stack {stack['title']} - no active cards")
                        continue
                    
                    # Create new webhook for each stack
                    webhook = DiscordWebhook(url=self.webhook_url, rate_limit_retry=True, thread_id=f"{self.thread_id}")
                    webhook.content = board_title if not first_message_sent else None
                    
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
                        # Split card descriptions if they exceed Discord's limit
                        combined_desc = '\n\n'.join(card_descriptions)
                        if len(combined_desc) > self.DISCORD_EMBED_LIMIT:
                            current_desc = []
                            current_length = 0
                            
                            for card_desc in card_descriptions:
                                desc_length = len(card_desc) + 2  # +2 for '\n\n'
                                if current_length + desc_length > self.DISCORD_EMBED_LIMIT:
                                    # Create and send current embed
                                    embed.description = '\n\n'.join(current_desc)
                                    webhook.add_embed(embed)
                                    if self.post_to_discord(webhook):
                                        first_message_sent = True
                                    
                                    # Create new webhook and embed for remaining cards
                                    webhook = DiscordWebhook(url=self.webhook_url, rate_limit_retry=True, thread_id=f"{self.thread_id}")
                                    embed = DiscordEmbed(
                                        title=f"{stack['title']} (continued)",
                                        color='03b2f8'
                                    )
                                    current_desc = [card_desc]
                                    current_length = desc_length
                                else:
                                    current_desc.append(card_desc)
                                    current_length += desc_length
                            
                            # Send remaining cards
                            if current_desc:
                                embed.description = '\n\n'.join(current_desc)
                                webhook.add_embed(embed)
                                if self.post_to_discord(webhook):
                                    first_message_sent = True
                        else:
                            # If description is within limits, send as single embed
                            embed.description = combined_desc
                            webhook.add_embed(embed)
                            if self.post_to_discord(webhook):
                                first_message_sent = True
                    
                except Exception as e:
                    self.logger.error(f"Error processing stack {stack.get('id')}: {str(e)}")
                    continue
                    
            if not first_message_sent:
                self.logger.info("No active cards found in any stack")
                
        except Exception as e:
            self.logger.error(f"Error creating Discord messages: {str(e)}")

    def post_to_discord(self, webhook: DiscordWebhook) -> bool:
        """Post webhook to Discord channel safely"""
        try:
            response = webhook.execute()
            if response:
                self.logger.info("Successfully posted update to Discord")
                # Add small delay between messages to avoid rate limiting
                time.sleep(1)
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
                        self.create_and_send_discord_messages(board, stacks)
                        self.last_etag = current_etag
                else:
                    self.logger.debug(f"No updates found at {datetime.now()}")
                
            except Exception as e:
                self.logger.error(f"Error in monitor loop: {str(e)}")
            finally:
                time.sleep(self.check_interval)


if __name__ == "__main__":
    try:
        #load_dotenv() #for testing
        bot = DeckDiscordBot()
        bot.monitor_board()
    except Exception as e:
        logging.error(f"Fatal error: {str(e)}")

