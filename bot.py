"""
Personal Reddit Analyzer Telegram Bot
Analyzes Reddit posts and comments using OpenAI API
"""

import os
import json
import time
import logging
import threading
from dotenv import load_dotenv
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Set
import concurrent.futures

import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
import praw
import prawcore
import openai
import zai
from apscheduler.schedulers.background import BackgroundScheduler


load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('bot.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class Config:
    """Configuration management"""
    def __init__(self):
        self.telegram_token = os.getenv('TELEGRAM_BOT_TOKEN', '')
        self.openai_api_key = os.getenv('OPENAI_API_KEY', '')
        self.openai_base_url = os.getenv('OPENAI_BASE_URL', '')
        self.use_zai = os.getenv('USE_ZAI', 'false')
        self.zai_api_key = os.getenv('ZAI_API_KEY', '')
        self.model_name = os.getenv('MODEL_NAME', '')
        self.reddit_client_id = os.getenv('REDDIT_CLIENT_ID', '')
        self.reddit_client_secret = os.getenv('REDDIT_CLIENT_SECRET', '')
        self.reddit_user_agent = os.getenv('REDDIT_USER_AGENT', 'RedditAnalyzerBot/1.0')
        
        # File paths
        self.subreddits_file = 'subreddits.txt'
        self.prompt_file = 'prompt.txt'
        
        self._load_subreddits()
        self._load_prompt()
    
    def _load_subreddits(self):
        """Load subreddits from file"""
        try:
            with open(self.subreddits_file, 'r', encoding='utf-8') as f:
                self.subreddits = [line.strip() for line in f if line.strip()]
        except FileNotFoundError:
            self.subreddits = ['Python', 'MachineLearning', 'Programming']
            self._save_subreddits()
    
    def _save_subreddits(self):
        """Save subreddits to file"""
        with open(self.subreddits_file, 'w', encoding='utf-8') as f:
            f.write('\n'.join(self.subreddits))
    
    def _load_prompt(self):
        """Load analysis prompt from file"""
        try:
            with open(self.prompt_file, 'r', encoding='utf-8') as f:
                self.analysis_prompt = f.read().strip()
        except FileNotFoundError:
            self.analysis_prompt = """
Analyze the following Reddit post and comments. Extract and summarize:

1. **Key Insights**: New information or important discoveries
2. **Interesting Discussions**: Notable debates or conversations
3. **Useful Tips**: Practical advice or recommendations
4. **Notable Perspectives**: Unique opinions or viewpoints
5. **Trending Topics**: Popular or controversial subjects

Provide a concise, well-structured summary highlighting the most valuable content.
Focus on information that would be useful and interesting to someone following this topic.
Use clear sections and bullet points for readability.

If the content is not particularly noteworthy, briefly explain why and provide a short summary instead.
            """
            self._save_prompt()
    
    def _save_prompt(self):
        """Save current prompt to file"""
        with open(self.prompt_file, 'w', encoding='utf-8') as f:
            f.write(self.analysis_prompt)
    
    def add_subreddit(self, subreddit: str):
        """Add a new subreddit"""
        if subreddit not in self.subreddits:
            self.subreddits.append(subreddit)
            self._save_subreddits()
    
    def remove_subreddit(self, subreddit: str):
        """Remove a subreddit"""
        if subreddit in self.subreddits:
            self.subreddits.remove(subreddit)
            self._save_subreddits()
    
    def set_subreddits(self, subreddits: List[str]):
        """Set the complete list of subreddits"""
        self.subreddits = subreddits
        self._save_subreddits()

class RedditAnalyzer:
    """Reddit data fetcher and analyzer with persistent state"""
    
    def __init__(self, config: Config):
        self.config = config
        self.reddit = praw.Reddit(
            client_id=config.reddit_client_id,
            client_secret=config.reddit_client_secret,
            user_agent=config.reddit_user_agent
        )
        if config.use_zai == "false":
            self.openai_client = openai.OpenAI(
                api_key=config.openai_api_key,
                base_url=config.openai_base_url,
            )
        else:
            self.zai_client = zai.ZaiClient(
                api_key=config.zai_api_key,
            )

        self.processed_posts_file = 'processed_posts.txt'
        self.processed_posts: Set[str] = self._load_processed_posts()
        self.lock = threading.Lock()

    def _load_processed_posts(self) -> Set[str]:
        """Load processed post IDs from a file."""
        try:
            with open(self.processed_posts_file, 'r', encoding='utf-8') as f:
                return {line.strip() for line in f if line.strip()}
        except FileNotFoundError:
            logger.info(f"'{self.processed_posts_file}' not found. Starting with an empty set.")
            return set()

    def _save_processed_posts(self):
        """Save processed post IDs to a file."""
        with self.lock:
            try:
                with open(self.processed_posts_file, 'w', encoding='utf-8') as f:
                    for post_id in self.processed_posts:
                        f.write(f"{post_id}\n")
            except IOError as e:
                logger.error(f"Failed to save processed posts: {e}")

    def fetch_posts(self, subreddit_name: str, limit: int = 8) -> List[Dict]:
        """Fetch recent posts from a subreddit"""
        try:
            subreddit = self.reddit.subreddit(subreddit_name)
            posts = []
            
            for submission in subreddit.hot(limit=limit):
                if submission.id in self.processed_posts:
                    continue
                
                if time.time() - submission.created_utc > 86400: # Older than 24 hours
                    continue
                
                submission.comments.replace_more(limit=5)
                comments = []
                for comment in submission.comments.list()[:15]:
                    if hasattr(comment, 'body') and len(comment.body) > 10 and comment.body != '[deleted]':
                        comments.append({
                            'author': str(comment.author) if comment.author else 'Unknown',
                            'body': comment.body[:800],
                            'score': comment.score
                        })
                
                if submission.score > 5 or len(comments) > 2:
                    post_data = {
                        'id': submission.id, 'title': submission.title, 'selftext': submission.selftext[:1000],
                        'url': submission.url, 'score': submission.score, 'num_comments': submission.num_comments,
                        'created_utc': submission.created_utc, 'subreddit': subreddit_name,
                        'permalink': submission.permalink, 'comments': comments
                    }
                    posts.append(post_data)
                    with self.lock:
                        self.processed_posts.add(submission.id)
            
            if posts: # Save only if new posts were found
                self._save_processed_posts()
            
            return posts
        
        except prawcore.exceptions.PrawcoreException as e:
            logger.error(f"PRAW error fetching from r/{subreddit_name}: {e}")
            return []
        except Exception as e:
            logger.error(f"Unexpected error fetching posts from r/{subreddit_name}: {e}")
            return []

    def analyze_posts_batch(self, posts: List[Dict]) -> Optional[str]:
        """Analyze multiple posts in a single AI request"""
        if not posts:
            return None

        combined_content = ""
        for idx, post in enumerate(posts, 1):
            post_text = f"""
POST #{idx}:
TITLE: {post['title']}
SUBREDDIT: r/{post['subreddit']}
SCORE: {post['score']} upvotes | {post['num_comments']} comments
TIME: {datetime.fromtimestamp(post['created_utc']).strftime('%Y-%m-%d %H:%M')}
URL: https://www.reddit.com{post['permalink']}

POST CONTENT:
{post['selftext'] if post['selftext'] else 'No text content (link post)'}

TOP COMMENTS:
"""
            sorted_comments = sorted(post['comments'], key=lambda x: x['score'], reverse=True)
            for i, comment in enumerate(sorted_comments[:8], 1):
                post_text += f"\n{i}. [↑{comment['score']}] u/{comment['author']}: {comment['body']}\n"
            combined_content += post_text + "\n\n"

        try:
            if self.config.use_zai == "false":
                response = self.openai_client.chat.completions.create(
                    model=self.config.model_name,
                    messages=[
                        {"role": "system", "content": self.config.analysis_prompt},
                        {"role": "user", "content": f"CONTENT TO ANALYZE:\n{combined_content}"}
                    ], max_tokens=4000, temperature=0.7
                )
            else:
                response = self.zai_client.chat.completions.create(
                    model=self.config.model_name,
                    messages=[
                        {"role": "system", "content": self.config.analysis_prompt},
                        {"role": "user", "content": f"CONTENT TO ANALYZE:\n{combined_content}"}
                    ], thinking={"type": "disabled"}, max_tokens=4000, temperature=0.7
                )
            
            analysis = response.choices[0].message.content.strip()
            return analysis if analysis else None

        except openai.APIError as e:
            logger.error(f"OpenAI API error: {e}")
            return f"Error: Could not analyze posts due to an AI API error: {e}"
        except Exception as e:
            logger.error(f"Unexpected error during AI analysis: {e}")
            return "Error: An unexpected error occurred during analysis."

class TelegramBot:
    """Main Telegram bot class"""
    
    def __init__(self, config: Config):
        self.config = config
        self.bot = telebot.TeleBot(config.telegram_token)
        self.reddit_analyzer = RedditAnalyzer(config)
        self.scheduler = BackgroundScheduler(timezone="UTC")
        self._setup_handlers()
        self._start_scheduler()
    
    def _run_analysis_in_thread(self, chat_id):
        """Helper to run analysis in a new thread to avoid blocking the bot."""
        analysis_thread = threading.Thread(target=self._perform_analysis, args=(chat_id,))
        analysis_thread.start()

    def _setup_handlers(self):
        """Setup bot command and callback handlers"""
        @self.bot.message_handler(commands=['start'])
        def send_welcome(message):
            welcome_text = (
                f"<b>🤖 Personal Reddit Analyzer Bot</b>\n\n"
                f"I analyze Reddit posts and comments to extract valuable insights using AI!\n\n"
                f"<b>Commands:</b>\n"
                f"• /start - Show this welcome message\n"
                f"• /analyze - Manually trigger analysis now\n"
                f"• /subreddits - View and manage your subreddits\n"
                f"• /status - Check bot status and statistics\n\n"
                f"I automatically analyze posts every 2 hours.\n\n"
                f"<b>Current Subreddits:</b> {', '.join(f'r/{sub}' for sub in self.config.subreddits)}"
            )
            keyboard = InlineKeyboardMarkup()
            keyboard.row(
                InlineKeyboardButton("🔄 Analyze Now", callback_data="analyze_now"),
                InlineKeyboardButton("📋 Manage Subreddits", callback_data="manage_subreddits")
            )
            self.bot.send_message(message.chat.id, welcome_text, reply_markup=keyboard, parse_mode='HTML')
        
        @self.bot.message_handler(commands=['analyze'])
        def manual_analyze(message):
            self.bot.reply_to(message, "🔄 Analysis has been started in the background. I'll send the results shortly.")
            self._run_analysis_in_thread(message.chat.id)
        
        @self.bot.message_handler(commands=['subreddits'])
        def show_subreddits(message):
            self._show_subreddit_manager(message.chat.id)
        
        @self.bot.message_handler(commands=['status'])
        def show_status(message):
            subreddits_list = '\n'.join(f'• r/{sub}' for sub in self.config.subreddits)

            status_text = (
    f"<b>📊 Bot Status</b>\n\n"
    f"🔹 <b>Active Subreddits:</b> {len(self.config.subreddits)}\n"
    f"🔹 <b>Processed Posts (since last restart):</b> {len(self.reddit_analyzer.processed_posts)}\n"
    f"🔹 <b>Auto-Analysis:</b> Every 2 hours\n\n"
    f"<b>Monitored Subreddits:</b>\n"
    f"{subreddits_list}"
)

            keyboard = InlineKeyboardMarkup()
            keyboard.add(InlineKeyboardButton("🔄 Analyze Now", callback_data="analyze_now"))
            self.bot.send_message(message.chat.id, status_text, reply_markup=keyboard, parse_mode='HTML')
        
        @self.bot.message_handler(commands=['settings'])
        def show_settings(message):
            self.bot.send_message(message.chat.id,
                "<b>⚙️ Bot Settings</b>\n\n"
                "📝 <b>Analysis Prompt:</b> Loaded from `prompt.txt`\n"
                "📋 <b>Subreddits:</b> Loaded from `subreddits.txt`\n\n"
                "You can edit these files directly to customize the bot's behavior.",
                parse_mode='HTML'
            )

        @self.bot.callback_query_handler(func=lambda call: True)
        def callback_query(call):
            if call.data == "manage_subreddits":
                self._show_subreddit_manager(call.message.chat.id, call.message.message_id)
            elif call.data == "analyze_now":
                self.bot.answer_callback_query(call.id, "Starting analysis in the background...")
                self._run_analysis_in_thread(call.message.chat.id)
            elif call.data == "edit_subreddits":
                msg = self.bot.send_message(call.message.chat.id,
                    "<b>📝 Replace Subreddit List</b>\n\nSend a comma-separated list of new subreddits (e.g., Python,datascience,learnpython).",
                    parse_mode='HTML'
                )
                self.bot.register_next_step_handler(msg, self._process_subreddit_update)
            elif call.data == "add_subreddit":
                msg = self.bot.send_message(call.message.chat.id,
                    "<b>➕ Add Subreddit</b>\n\nSend the name of the subreddit to add (e.g., MachineLearning).",
                    parse_mode='HTML'
                )
                self.bot.register_next_step_handler(msg, self._process_add_subreddit)
            elif call.data == "remove_subreddit":
                self._show_remove_subreddit_menu(call.message.chat.id, call.message.message_id)
            elif call.data.startswith("delete_sub_"):
                subreddit_to_delete = call.data.split('_', 2)[2]
                self.config.remove_subreddit(subreddit_to_delete)
                self.bot.answer_callback_query(call.id, f"✅ Removed r/{subreddit_to_delete}")
                self._show_remove_subreddit_menu(call.message.chat.id, call.message.message_id)

    def _show_subreddit_manager(self, chat_id, message_id=None):
        if self.config.subreddits:
            subreddits_list = '\n'.join(f'• r/{sub}' for sub in self.config.subreddits)
        else:
            subreddits_list = 'None'

        text = (
    f"<b>📋 Subreddit Manager</b>\n\n"
    f"<b>Currently monitoring:</b>\n"
    f"{subreddits_list}\n\n"
    f"<b>Total:</b> {len(self.config.subreddits)} subreddits"
)

        keyboard = InlineKeyboardMarkup()
        keyboard.row(
            InlineKeyboardButton("➕ Add", callback_data="add_subreddit"),
            InlineKeyboardButton("➖ Remove", callback_data="remove_subreddit")
        )
        keyboard.add(InlineKeyboardButton("✏️ Replace All", callback_data="edit_subreddits"))
        
        try:
            if message_id:
                self.bot.edit_message_text(text, chat_id, message_id, reply_markup=keyboard, parse_mode='HTML')
            else:
                self.bot.send_message(chat_id, text, reply_markup=keyboard, parse_mode='HTML')
        except telebot.apihelper.ApiTelegramException as e:
            if "message is not modified" in str(e):
                pass
            else:
                logger.error(f"Error showing subreddit manager: {e}")
                self.bot.send_message(chat_id, text, reply_markup=keyboard, parse_mode='HTML')

    def _show_remove_subreddit_menu(self, chat_id, message_id):
        text = "<b>➖ Remove Subreddit</b>\n\nSelect a subreddit to remove:"
        keyboard = InlineKeyboardMarkup()
        for subreddit in self.config.subreddits:
            keyboard.add(InlineKeyboardButton(f"❌ r/{subreddit}", callback_data=f"delete_sub_{subreddit}"))
        keyboard.add(InlineKeyboardButton("🔙 Back to Manager", callback_data="manage_subreddits"))
        
        try:
            self.bot.edit_message_text(text, chat_id, message_id, reply_markup=keyboard, parse_mode='HTML')
        except telebot.apihelper.ApiTelegramException as e:
            if "message is not modified" in str(e):
                self.bot.answer_callback_query(call.id, "List is already up to date.")
            else:
                logger.error(f"Error editing message for remove menu: {e}")
                self.bot.send_message(chat_id, text, reply_markup=keyboard, parse_mode='HTML')

    def _process_subreddit_update(self, message):
        try:
            subreddits = [sub.strip() for sub in message.text.split(',') if sub.strip()]
            if not subreddits:
                self.bot.reply_to(message, "❌ Invalid input. Please provide at least one subreddit.")
                return
            self.config.set_subreddits(subreddits)
            response_text = "<b>✅ Subreddit List Updated!</b>\n\n<b>Now monitoring:</b>\n" + "\n".join(f"• r/{sub}" for sub in subreddits)
            self.bot.reply_to(message, response_text, parse_mode='HTML')
        except Exception as e:
            logger.error(f"Error updating subreddits: {e}")
            self.bot.reply_to(message, "❌ An error occurred. Please try again.")
    
    def _process_add_subreddit(self, message):
        try:
            subreddit = message.text.strip().split(" ")[0] # Take first word to be safe
            if not subreddit:
                self.bot.reply_to(message, "❌ Invalid input. Please provide a subreddit name.")
                return
            if subreddit in self.config.subreddits:
                self.bot.reply_to(message, f"📋 r/{subreddit} is already being monitored.")
                return
            self.config.add_subreddit(subreddit)
            self.bot.reply_to(message, f"✅ Added r/{subreddit} to your monitoring list!")
        except Exception as e:
            logger.error(f"Error adding subreddit: {e}")
            self.bot.reply_to(message, "❌ An error occurred. Please try again.")
        
    def _send_long_message(self, chat_id, text, **kwargs):
        """Splits a long message into multiple parts."""
        max_length = 4096
        if len(text) <= max_length:
            self.bot.send_message(chat_id, text, **kwargs)
            return
        
        parts = []
        while len(text) > 0:
            if len(text) > max_length:
                part = text[:max_length]
                last_newline = part.rfind('\n')
                if last_newline != -1:
                    parts.append(text[:last_newline])
                    text = text[last_newline+1:]
                else:
                    parts.append(text[:max_length])
                    text = text[max_length:]
            else:
                parts.append(text)
                break
        
        for i, part in enumerate(parts):
            if i > 0:
                self.bot.send_message(chat_id, f"<b>...continued</b>\n\n{part}", **kwargs)
            else:
                self.bot.send_message(chat_id, part, **kwargs)
            time.sleep(1)

    def _perform_analysis(self, chat_id):
        logger.info(f"Starting analysis for chat_id: {chat_id}")
        self.bot.send_message(chat_id, f"🔍 <b>Starting Analysis</b> for {len(self.config.subreddits)} subreddits...", parse_mode='HTML')
        
        total_new_posts = 0
        summary_lines = []
        
        for subreddit in self.config.subreddits:
            try:
                posts = self.reddit_analyzer.fetch_posts(subreddit, limit=8)
                if not posts:
                    summary_lines.append(f"• r/{subreddit}: No new posts found.")
                    continue

                summary_lines.append(f"• r/{subreddit}: Found {len(posts)} new posts, analyzing...")
                self.bot.send_message(chat_id, f"Found {len(posts)} new post(s) in r/{subreddit}. Analyzing now...")
                
                analysis = self.reddit_analyzer.analyze_posts_batch(posts)
                if analysis:
                    self._send_long_message(chat_id, analysis, parse_mode='HTML', disable_web_page_preview=True)
                    total_new_posts += len(posts)
                else:
                    self.bot.send_message(chat_id, f"Could not generate a summary for r/{subreddit}.")
                
                time.sleep(2) # Avoid rate limiting
            except Exception as e:
                logger.critical(f"A critical error occurred while processing r/{subreddit}: {e}", exc_info=True)
                self.bot.send_message(chat_id, f"⚠️ An unexpected error occurred while processing r/{subreddit}. Check logs.")
        
        final_summary = "✅ <b>Analysis Complete!</b>\n\n" + "\n".join(summary_lines)
        if total_new_posts == 0:
            final_summary += "\n\n📭 No new interesting posts found across all subreddits."

        self.bot.send_message(chat_id, final_summary, parse_mode='HTML')
        logger.info(f"Finished analysis for chat_id: {chat_id}")

    def _start_scheduler(self):
        self.scheduler.add_job(
            func=self._scheduled_analysis,
            trigger="interval",
            hours=2,
            id='reddit_analysis'
        )
        self.scheduler.start()
        logger.info("Scheduler started - will analyze posts every 2 hours.")
    
    def _scheduled_analysis(self):
        logger.info("Starting scheduled Reddit analysis...")
        personal_chat_id = os.getenv('PERSONAL_CHAT_ID')
        if personal_chat_id:
            try:
                self._perform_analysis(int(personal_chat_id))
            except Exception as e:
                logger.error(f"Error in scheduled analysis task: {e}", exc_info=True)
        else:
            logger.warning("PERSONAL_CHAT_ID not set - skipping scheduled analysis.")
    
    def run(self):
        logger.info("Starting Personal Reddit Analyzer Bot...")
        try:
            self.bot.infinity_polling(timeout=20, long_polling_timeout=10, logger_level=logging.WARNING)
        except Exception as e:
            logger.critical(f"Bot polling CRASHED: {e}", exc_info=True)
            time.sleep(15) # Wait before restarting

if __name__ == "__main__":
    while True:
        try:
            config = Config()
            bot = TelegramBot(config)
            bot.run()
        except Exception as main_exc:
            logger.critical(f"Main loop failed: {main_exc}. Restarting in 30 seconds...", exc_info=True)
            time.sleep(30)