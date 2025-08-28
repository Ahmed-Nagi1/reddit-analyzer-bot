"""
Setup script for Reddit Analyzer Bot with colored output
"""

import os
import sys
import subprocess

# ANSI color codes
class Colors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKCYAN = '\033[96m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'
    RESET = '\033[0m'

def create_env_file():
    """Create .env file if it doesn't exist"""
    if not os.path.exists('.env'):
        print(f"{Colors.OKBLUE}Creating .env file...{Colors.RESET}")
        with open('.env', 'w') as f:
            f.write("""# Telegram Bot Configuration
TELEGRAM_BOT_TOKEN=your_telegram_bot_token_here

# OpenAI Configuration  
OPENAI_API_KEY=your_openai_api_key_here
OPENAI_BASE_URL=https://api.openai.com/v1

# z.ai configuration for free GLM-4.5-Flash model (Optional)
USE_ZAI=false  # true or false
ZAI_API_KEY=your_zai_api_key_here

MODEL_NAME=your_model_name

# Reddit API Configuration
REDDIT_CLIENT_ID=your_reddit_client_id_here
REDDIT_CLIENT_SECRET=your_reddit_client_secret_here
REDDIT_USER_AGENT=RedditAnalyzerBot/1.0

# Personal Chat ID (get this by messaging your bot and checking logs)
PERSONAL_CHAT_ID=your_telegram_chat_id_here
""")
        print(f"{Colors.OKGREEN}✅ Created .env file - please fill in your API credentials{Colors.RESET}")
    else:
        print(f"{Colors.OKGREEN}✅ .env file already exists{Colors.RESET}")

def create_config_files():
    """Create default config files if they don't exist"""
    if not os.path.exists('subreddits.txt'):
        print(f"{Colors.OKBLUE}Creating subreddits.txt...{Colors.RESET}")
        with open('subreddits.txt', 'w') as f:
            f.write("Programming\nTechnology")
        print(f"{Colors.OKGREEN}✅ Created subreddits.txt with default subreddits{Colors.RESET}")
    else:
        print(f"{Colors.OKGREEN}✅ subreddits.txt already exists{Colors.RESET}")
    
    if not os.path.exists('prompt.txt'):
        print(f"{Colors.OKBLUE}Creating prompt.txt...{Colors.RESET}")
        with open('prompt.txt', 'w') as f:
            f.write("""
Start your summary with name of community

Analyze the following Reddit post and comments. Extract and summarize:

1. **Key Insights**: New information, discoveries, or important findings
2. **Interesting Discussions**: Notable debates, conversations, or different viewpoints  
3. **Useful Tips**: Practical advice, recommendations, or how-to information
4. **Notable Perspectives**: Unique opinions, expert insights, or thought-provoking ideas
5. **Trending Topics**: Popular subjects, controversial issues, or emerging trends

Format your response with clear sections and use bullet points for readability.
Focus on information that would be valuable and interesting to someone following this topic.
Be concise but comprehensive - aim for a summary that captures the essence without being too lengthy.

If the content doesn't contain particularly noteworthy information, briefly explain why and provide a short summary instead.

Prioritize:
- Actionable information
- Expert opinions or insider knowledge  
- Breaking news or updates
- Technical insights or tutorials
- Community discussions with high engagement

You are a telegram bot.  
- Output: single string, ≤4000 characters, ready for Telegram HTML.  
-Format roles:
    Use only the supported tags: <b>, <i>, <u>, <s>, <em>, <code>, <pre>, <strong>, <blockquote>, <a href="URL">.

    Do NOT use any unsupported tags such as <ul>, <li>, <div>, <span>, <h1>, etc.

    Ensure all tags are properly closed: every opening tag must have a matching closing tag.

    Before sending the message, clean the text from any unsupported or unclosed tags.

    If the text contains unsupported or incorrectly closed tags, reformat the text according to the rules above to avoid Telegram errors:

    Bad Request: can't parse entities: Unmatched end tag

    Bad Request: can't parse entities: Unexpected end tag

    Goal: Ensure the text is valid for Telegram and won’t cause any tag parsing errors.""")
        print(f"{Colors.OKGREEN}✅ Created prompt.txt with default analysis prompt{Colors.RESET}")
    else:
        print(f"{Colors.OKGREEN}✅ prompt.txt already exists{Colors.RESET}")

def install_requirements():
    """Install packages from requirements.txt in a virtual environment."""
    venv_path = os.path.join(os.getcwd(), ".venv")
    if not os.path.exists(venv_path):
        print(f"{Colors.OKBLUE}Creating virtual environment...{Colors.RESET}")
        subprocess.run([sys.executable, "-m", "venv", ".venv"], check=True)

    print(f"{Colors.OKBLUE}Installing requirements...{Colors.RESET}")
    pip_path = os.path.join(venv_path, "bin" if os.name != "nt" else "Scripts", "pip")
    try:
        subprocess.run([pip_path, "install", "-r", "requirements.txt"], check=True)
        print(f"{Colors.OKGREEN}✅ Requirements installed{Colors.RESET}")
    except subprocess.CalledProcessError:
        print(f"{Colors.FAIL}❌ Failed to install requirements{Colors.RESET}")
        sys.exit(1)

def main():
    print(f"{Colors.HEADER}🤖 Setting up Reddit Analyzer Bot...{Colors.RESET}")
    
    create_env_file()
    create_config_files()
    
    if os.path.exists('requirements.txt'):
        install_requirements()
    else:
        print(f"{Colors.WARNING}⚠️  requirements.txt not found - skipping package installation{Colors.RESET}")
    
    print(f"\n{Colors.OKGREEN}🎉 Setup complete!{Colors.RESET}")
    print(f"\n{Colors.BOLD}📝 Next steps:{Colors.RESET}")
    print(f"{Colors.OKCYAN}1. Edit .env file with your API credentials")
    print("2. Get Telegram Bot token from @BotFather")
    print("3. Get Reddit API credentials from https://reddit.com/prefs/apps")
    print("4. Get OpenAI API key from https://platform.openai.com")
    print("5. Start the bot with: python bot.py")
    print("6. Message your bot to get your PERSONAL_CHAT_ID and add it to .env{Colors.RESET}")

if __name__ == "__main__":
    main()
