#!/usr/bin/env python3
"""
Setup script for Reddit Analyzer Bot
"""

import os
import sys
import subprocess

def create_env_file():
    """Create .env file if it doesn't exist"""
    if not os.path.exists('.env'):
        print("Creating .env file...")
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
        print("✅ Created .env file - please fill in your API credentials")
    else:
        print("✅ .env file already exists")

def create_config_files():
    """Create default config files if they don't exist"""
    
    # Create subreddits.txt
    if not os.path.exists('subreddits.txt'):
        print("Creating subreddits.txt...")
        with open('subreddits.txt', 'w') as f:
            f.write("""Programming
Technology""")
        print("✅ Created subreddits.txt with default subreddits")
    else:
        print("✅ subreddits.txt already exists")
    
    # Create prompt.txt
    if not os.path.exists('prompt.txt'):
        print("Creating prompt.txt...")
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

    Use <b> and <i> only for formatting headings, not for normal text or paragraphs.

    Before sending the message, clean the text from any unsupported or unclosed tags.

    If the text contains unsupported or incorrectly closed tags, reformat the text according to the rules above to avoid Telegram errors:

    Bad Request: can't parse entities: Unmatched end tag

    Bad Request: can't parse entities: Unexpected end tag

    Goal: Ensure the text is valid for Telegram and won’t cause any tag parsing errors.""")
        print("✅ Created prompt.txt with default analysis prompt")
    else:
        print("✅ prompt.txt already exists")



def install_requirements():
    """Install packages from requirements.txt in a virtual environment."""
    venv_path = os.path.join(os.getcwd(), ".venv")
    
    # Check if virtual environment exists, create if not
    if not os.path.exists(venv_path):
        print("Creating virtual environment...")
        subprocess.run([sys.executable, "-m", "venv", ".venv"], check=True)

    print("Installing requirements...")
    # Path to pip in the virtual environment
    pip_path = os.path.join(venv_path, "bin" if os.name != "nt" else "Scripts", "pip")
    # Use subprocess.run for better error handling
    try:
        subprocess.run([pip_path, "install", "-r", "requirements.txt"], check=True)
        print("✅ Requirements installed")
    except subprocess.CalledProcessError:
        print("❌ Failed to install requirements")
        sys.exit(1)

def main():
    """Main setup function"""
    print("🤖 Setting up Reddit Analyzer Bot...")
    
    create_env_file()
    create_config_files()
    
    if os.path.exists('requirements.txt'):
        install_requirements()
    else:
        print("⚠️  requirements.txt not found - skipping package installation")
    
    print("\n🎉 Setup complete!")
    print("\n📝 Next steps:")
    print("1. Edit .env file with your API credentials")
    print("2. Get Telegram Bot token from @BotFather")
    print("3. Get Reddit API credentials from https://reddit.com/prefs/apps")
    print("4. Get OpenAI API key from https://platform.openai.com")
    print("5. Start the bot with: python bot.py")
    print("6. Message your bot to get your PERSONAL_CHAT_ID and add it to .env")

if __name__ == "__main__":
    main()