# Personal Reddit Analyzer Bot

A Telegram bot that monitors Reddit subreddits and analyzes posts/comments using AI to provide insightful summaries.

## Features

- **Automated Reddit Monitoring**: Tracks multiple subreddits for new and trending content
- **AI-Powered Analysis**: Uses OpenAI or z.ai to analyze posts and extract valuable insights
- **Telegram Integration**: Receive analysis summaries directly in your Telegram chat
- **Flexible Scheduling**: Manual analysis on demand or automatic analysis every 2 hours
- **Subreddit Management**: Easily add, remove, and manage your monitored subreddits
- **Customizable Prompts**: Modify analysis behavior through customizable prompts

## Installation

1. Clone the repository:
```bash
git clone https://github.com/Ahmed-Nagi1/reddit-analyzer-bot
cd reddit-analyzer-bot
```

2. Run the setup script:
```bash
python setup.py
```

This will:
- Create a virtual environment
- Install required dependencies
- Generate default configuration files

3. Configure your environment:
   - Edit the `.env` file with your API credentials
   - Customize `subreddits.txt` with your desired subreddits
   - Modify `prompt.txt` to customize the analysis behavior

## Setup and Configuration

### Required API Credentials

1. **Telegram Bot Token**
   - Get from [@BotFather](https://t.me/BotFather) on Telegram

2. **Reddit API Credentials**
   - Create at [Reddit Apps](https://www.reddit.com/prefs/apps)
   - Set redirect URI to `http://localhost:8080`

3. **AI API (Choose one)**
   - **OpenAI**: Get API key from [OpenAI Platform](https://platform.openai.com)
   - **z.ai**: Get API key for free GLM-4.5-Flash model


### Configuration Files

- **subreddits.txt**: List of subreddits to monitor (one per line)
- **prompt.txt**: Custom analysis prompt for the AI

## Usage

### Starting the Bot

```bash
python bot.py
```

### Interactive Features

- Inline buttons for quick actions
- Dynamic subreddit management
- Real-time analysis progress updates
- Formatted summaries with HTML support

## Example Workflow

1. Bot starts and loads configuration
2. Every 2 hours, bot fetches new posts from monitored subreddits
3. AI analyzes posts and extracts key insights
4. Bot sends formatted summaries to your Telegram chat
5. You can manually trigger analysis anytime

## Requirements

- Python 3.7+
- Internet connection
- Telegram account
- API credentials (Telegram, Reddit, and AI service)


## License

This project is open source and available under the [MIT License](LICENSE).
