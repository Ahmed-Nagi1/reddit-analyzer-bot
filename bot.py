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
from typing import List, Dict, Optional


import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
import praw
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
    """Reddit data fetcher and analyzer"""
    
    def __init__(self, config: Config):
        self.config = config
        self.reddit = praw.Reddit(
            client_id=config.reddit_client_id,
            client_secret=config.reddit_client_secret,
            user_agent=config.reddit_user_agent
        )
        if config.use_zai =="false":
            self.openai_client = openai.OpenAI(
                api_key=config.openai_api_key,
                base_url=config.openai_base_url,
            )
        else:
            self.zai_client = zai.ZaiClient(
                api_key=config.zai_api_key,
            )

        self.processed_posts = set()
    
    def fetch_posts(self, subreddit_name: str, limit: int = 10) -> List[Dict]:
        """Fetch recent posts from a subreddit"""
        try:
            subreddit = self.reddit.subreddit(subreddit_name)
            posts = []
            
            for submission in subreddit.hot(limit=limit):
                if submission.id in self.processed_posts:
                    continue
                
                # Skip if post is too old (older than 24 hours)
                if time.time() - submission.created_utc > 86400:
                    continue
                
                # Get comments
                submission.comments.replace_more(limit=5)
                comments = []
                for comment in submission.comments.list()[:15]:  # Limit comments
                    if hasattr(comment, 'body') and len(comment.body) > 10 and comment.body != '[deleted]':
                        comments.append({
                            'author': str(comment.author) if comment.author else 'Unknown',
                            'body': comment.body[:800],  # Truncate long comments
                            'score': comment.score
                        })
                
                # Only analyze posts with some engagement
                if submission.score > 5 or len(comments) > 2:
                    post_data = {
                        'id': submission.id,
                        'title': submission.title,
                        'selftext': submission.selftext[:1000],  # Truncate long posts
                        'url': submission.url,
                        'score': submission.score,
                        'num_comments': submission.num_comments,
                        'created_utc': submission.created_utc,
                        'subreddit': subreddit_name,
                        'permalink': submission.permalink,
                        'comments': comments
                    }
                    
                    posts.append(post_data)
                    self.processed_posts.add(submission.id)
            
            return posts
        
        except Exception as e:
            logger.error(f"Error fetching posts from r/{subreddit_name}: {e}")
            return []
    
    def analyze_post(self, post: Dict) -> Optional[str]:
        """Analyze a single post and its comments using OpenAI"""
        try:
            # Prepare content for analysis
            content = f"""
POST TITLE: {post['title']}
SUBREDDIT: r/{post['subreddit']}
SCORE: {post['score']} upvotes | {post['num_comments']} comments
TIME: {datetime.fromtimestamp(post['created_utc']).strftime('%Y-%m-%d %H:%M')}

POST CONTENT:
{post['selftext'] if post['selftext'] else 'No text content (link post)'}

TOP COMMENTS:
"""
            
            # Add top comments sorted by score
            sorted_comments = sorted(post['comments'], key=lambda x: x['score'], reverse=True)
            for i, comment in enumerate(sorted_comments[:8], 1):
                content += f"\n{i}. [↑{comment['score']}] u/{comment['author']}: {comment['body']}\n"
            
            # Get analysis from OpenAI
            try:
                if config.use_zai == "false":
                    response = self.openai_client.chat.completions.create(
                        model=config.model_name,
                        messages=[
                            {"role": "system", "content": self.config.analysis_prompt},
                            {"role": "user", "content": f"CONTENT TO ANALYZE:\n{content}"}
                        ],
                        max_tokens=800,
                        temperature=0.7
                    )
                else:
                    print("use zai")
                    response = self.zai_client.chat.completions.create(
                        model=config.model_name,
                        messages=[
                            {"role": "system", "content": self.config.analysis_prompt},
                            {"role": "user", "content": f"CONTENT TO ANALYZE:\n{content}"}
                        ],
                            thinking={
                                "type": "disabled",  # Optional: "disabled" or "enabled", default is "enabled"
                            },
                        max_tokens=800,
                        temperature=0.7
                    )

                analysis = response.choices[0].message.content.strip()
                
                if analysis:
                    # Format the response
                    header = f"📊 **r/{post['subreddit']} Analysis**\n"
                    header += f"**{post['title']}**\n"
                    header += f"🔗 [View Post](https://reddit.com{post['permalink']}) | ↑{post['score']} | 💬{post['num_comments']}\n\n"
                    
                    return header + analysis
                
            except Exception as e:
                logger.error(f"OpenAI API error: {e}")
                return None
            
            return None
        
        except Exception as e:
            logger.error(f"Error analyzing post {post['id']}: {e}")
            return None


class TelegramBot:
    """Main Telegram bot class"""
    
    def __init__(self, config: Config):
        self.config = config
        self.bot = telebot.TeleBot(config.telegram_token)
        self.reddit_analyzer = RedditAnalyzer(config)
        self.scheduler = BackgroundScheduler()
        
        self._setup_handlers()
        self._start_scheduler()
    
    def _setup_handlers(self):
        """Setup bot command and callback handlers"""
        
        @self.bot.message_handler(commands=['start'])
        def send_welcome(message):
            welcome_text = """
🤖 **Personal Reddit Analyzer Bot**

I analyze Reddit posts and comments to extract valuable insights using AI!

**Commands:**
• `/start` - Show this welcome message
• `/analyze` - Manually trigger analysis now
• `/subreddits` - View and manage your subreddits
• `/status` - Check bot status and statistics
• `/settings` - Bot settings and configuration

I automatically analyze posts every 2 hours and send you summaries of interesting content.

**Current Subreddits:** """ + ", ".join(f"r/{sub}" for sub in self.config.subreddits)
            
            keyboard = InlineKeyboardMarkup()
            keyboard.row(
                InlineKeyboardButton("🔄 Analyze Now", callback_data="analyze_now"),
                InlineKeyboardButton("📋 Manage Subreddits", callback_data="manage_subreddits")
            )
            
            self.bot.reply_to(message, welcome_text, reply_markup=keyboard, parse_mode='Markdown')
        
        @self.bot.message_handler(commands=['analyze'])
        def manual_analyze(message):
            self.bot.reply_to(message, "🔄 Starting analysis of your subreddits...")
            self._perform_analysis(message.chat.id)
        
        @self.bot.message_handler(commands=['subreddits'])
        def show_subreddits(message):
            text = f"📋 **Your Monitored Subreddits:**\n\n"
            for i, sub in enumerate(self.config.subreddits, 1):
                text += f"{i}. r/{sub}\n"
            
            keyboard = InlineKeyboardMarkup()
            keyboard.row(
                InlineKeyboardButton("✏️ Edit List", callback_data="edit_subreddits"),
                InlineKeyboardButton("➕ Add Subreddit", callback_data="add_subreddit")
            )
            
            self.bot.reply_to(message, text, reply_markup=keyboard, parse_mode='Markdown')
        
        @self.bot.message_handler(commands=['status'])
        def show_status(message):
            status_text = f"""
📊 **Bot Status**

🔹 **Active Subreddits:** {len(self.config.subreddits)}
🔹 **Processed Posts:** {len(self.reddit_analyzer.processed_posts)}
🔹 **Last Analysis:** Check logs for details
🔹 **Auto-Analysis:** Every 2 hours

**Monitored Subreddits:**
{chr(10).join(f'• r/{sub}' for sub in self.config.subreddits)}
            """
            
            keyboard = InlineKeyboardMarkup()
            keyboard.add(InlineKeyboardButton("🔄 Analyze Now", callback_data="analyze_now"))
            
            self.bot.reply_to(message, status_text, reply_markup=keyboard, parse_mode='Markdown')
        
        @self.bot.message_handler(commands=['settings'])
        def show_settings(message):
            settings_text = f"""
⚙️ **Bot Settings**

📝 **Analysis Prompt:** Loaded from `prompt.txt`
📋 **Subreddits:** Loaded from `subreddits.txt`

You can edit these files directly to customize the bot's behavior.
            """
            self.bot.reply_to(message, settings_text, parse_mode='Markdown')
        
        @self.bot.callback_query_handler(func=lambda call: True)
        def callback_query(call):
            if call.data == "manage_subreddits":
                self._show_subreddit_manager(call.message.chat.id)
            elif call.data == "analyze_now":
                self.bot.answer_callback_query(call.id, "Starting analysis...")
                self._perform_analysis(call.message.chat.id)
            elif call.data == "edit_subreddits":
                self.bot.send_message(
                    call.message.chat.id,
                    "📝 **Edit Subreddit List**\n\nSend me a comma-separated list of subreddits (without r/):\n\n**Example:** `Python,MachineLearning,Programming,DataScience`"
                )
                self.bot.register_next_step_handler_by_chat_id(
                    call.message.chat.id, self._process_subreddit_update
                )
            elif call.data == "add_subreddit":
                self.bot.send_message(
                    call.message.chat.id,
                    "➕ **Add Subreddit**\n\nSend me the name of the subreddit to add (without r/):\n\n**Example:** `Python`"
                )
                self.bot.register_next_step_handler_by_chat_id(
                    call.message.chat.id, self._process_add_subreddit
                )
        
        @self.bot.message_handler(func=lambda message: True)
        def handle_all_messages(message):
            self.bot.reply_to(
                message, 
                "👋 Use `/start` to see available commands, or `/analyze` to analyze Reddit posts now!"
            )
    
    def _show_subreddit_manager(self, chat_id):
        """Show subreddit management interface"""
        text = f"""
📋 **Subreddit Manager**

**Currently monitoring:**
{chr(10).join(f'• r/{sub}' for sub in self.config.subreddits)}

**Total:** {len(self.config.subreddits)} subreddits
        """
        
        keyboard = InlineKeyboardMarkup()
        keyboard.row(
            InlineKeyboardButton("✏️ Replace All", callback_data="edit_subreddits"),
            InlineKeyboardButton("➕ Add One", callback_data="add_subreddit")
        )
        
        self.bot.send_message(chat_id, text, reply_markup=keyboard, parse_mode='Markdown')
    
    def _process_subreddit_update(self, message):
        """Process subreddit list update"""
        try:
            subreddit_text = message.text.strip()
            subreddits = [sub.strip() for sub in subreddit_text.split(',') if sub.strip()]
            
            if not subreddits:
                self.bot.reply_to(message, "❌ Please provide at least one subreddit!")
                return
            
            self.config.set_subreddits(subreddits)
            
            response_text = f"✅ **Subreddit List Updated!**\n\n**Now monitoring:**\n"
            response_text += "\n".join(f"• r/{sub}" for sub in subreddits)
            
            self.bot.reply_to(message, response_text, parse_mode='Markdown')
        
        except Exception as e:
            logger.error(f"Error updating subreddits: {e}")
            self.bot.reply_to(message, "❌ Error updating subreddits. Please try again.")
    
    def _process_add_subreddit(self, message):
        """Process adding a single subreddit"""
        try:
            subreddit = message.text.strip()
            
            if not subreddit:
                self.bot.reply_to(message, "❌ Please provide a subreddit name!")
                return
            
            if subreddit in self.config.subreddits:
                self.bot.reply_to(message, f"📋 r/{subreddit} is already in your list!")
                return
            
            self.config.add_subreddit(subreddit)
            self.bot.reply_to(message, f"✅ Added r/{subreddit} to your monitoring list!")
        
        except Exception as e:
            logger.error(f"Error adding subreddit: {e}")
            self.bot.reply_to(message, "❌ Error adding subreddit. Please try again.")
    
    def _perform_analysis(self, chat_id):
        """Perform Reddit analysis and send results"""
        try:
            self.bot.send_message(
                chat_id, 
                f"🔍 **Starting Analysis**\n\nAnalyzing posts from: {', '.join(f'r/{sub}' for sub in self.config.subreddits)}"
            )
            
            total_analyses = 0
            for subreddit in self.config.subreddits:
                try:
                    self.bot.send_message(chat_id, f"📡 Fetching from r/{subreddit}...")
                    posts = self.reddit_analyzer.fetch_posts(subreddit, limit=10)
                    
                    if not posts:
                        continue
                    
                    for post in posts:
                        analysis = self.reddit_analyzer.analyze_post(post)
                        if analysis:
                            # Split long messages if needed
                            if len(analysis) > 4000:
                                parts = [analysis[i:i+3800] for i in range(0, len(analysis), 3800)]
                                for i, part in enumerate(parts):
                                    if i == 0:
                                        self.bot.send_message(chat_id, part, parse_mode='Markdown', disable_web_page_preview=True)
                                    else:
                                        self.bot.send_message(chat_id, f"**...continued**\n\n{part}", parse_mode='Markdown')
                            else:
                                self.bot.send_message(chat_id, analysis, parse_mode='Markdown', disable_web_page_preview=True)
                            
                            total_analyses += 1
                            time.sleep(2)  # Rate limiting between messages
                
                except Exception as e:
                    logger.error(f"Error analyzing r/{subreddit}: {e}")
                    self.bot.send_message(chat_id, f"⚠️ Error analyzing r/{subreddit}: {str(e)}")
                    continue
            
            # Summary message
            if total_analyses == 0:
                self.bot.send_message(chat_id, "📭 **No New Content**\n\nNo new interesting posts found in your monitored subreddits.")
            else:
                self.bot.send_message(chat_id, f"✅ **Analysis Complete!**\n\nProcessed {total_analyses} interesting posts.")
        
        except Exception as e:
            logger.error(f"Error in analysis: {e}")
            self.bot.send_message(chat_id, f"❌ **Analysis Error**\n\n{str(e)}")
    
    def _start_scheduler(self):
        """Start the background scheduler"""
        self.scheduler.add_job(
            func=self._scheduled_analysis,
            trigger="interval",
            hours=2,
            id='reddit_analysis'
        )
        self.scheduler.start()
        logger.info("Scheduler started - will analyze posts every 2 hours")
    
    def _scheduled_analysis(self):
        """Perform scheduled analysis"""
        logger.info("Starting scheduled Reddit analysis")
        
        try:
            # You'll need to set your personal chat ID here
            # You can get it by messaging the bot and checking the logs
            personal_chat_id = os.getenv('PERSONAL_CHAT_ID')
            
            if personal_chat_id:
                self._perform_analysis(int(personal_chat_id))
            else:
                logger.warning("PERSONAL_CHAT_ID not set - skipping scheduled analysis")
        
        except Exception as e:
            logger.error(f"Error in scheduled analysis: {e}")
    
    def run(self):
        """Start the bot"""
        logger.info("Starting Personal Reddit Analyzer Bot...")
        try:
            self.bot.infinity_polling(timeout=10, long_polling_timeout=5)
        except Exception as e:
            logger.error(f"Bot polling error: {e}")

if __name__ == "__main__":
    config = Config()
    bot = TelegramBot(config)
    bot.run()
    print("Bot started...")
