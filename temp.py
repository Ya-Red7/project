import os
import time
import telebot
import requests
from flask import Flask, request
from datetime import datetime
from dotenv import load_dotenv
import json

# Load environment variables
load_dotenv()

# Get API tokens from environment variables
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
ODDS_API_KEY = os.getenv("ODDS_API_KEY")
API_NBA_KEY = os.getenv("API_NBA_KEY")  # Replace with a valid API key for live scores

# Initialize the Telegram bot
bot = telebot.TeleBot(BOT_TOKEN)

# Initialize Flask app
app = Flask(__name__)

# Global variable for tracking teams
team_names = set()  # Store multiple selected teams

# Inline keyboard setup for team selection
@bot.message_handler(commands=['set_team'])
def set_team(message):
    markup = telebot.types.InlineKeyboardMarkup(row_width=5)
    teams = [
        ("Atlanta Hawks", "Atlanta Hawks"),
        ("Boston Celtics", "Boston Celtics"),
        ("Brooklyn Nets", "Brooklyn Nets"),
        ("Charlotte Hornets", "Charlotte Hornets"),
        ("Chicago Bulls", "Chicago Bulls"),
        ("Cleveland Cavaliers", "Cleveland Cavaliers"),
        ("Dallas Mavericks", "Dallas Mavericks"),
        ("Denver Nuggets", "Denver Nuggets"),
        ("Detroit Pistons", "Detroit Pistons"),
        ("Golden State Warriors", "Golden State Warriors"),
        ("Houston Rockets", "Houston Rockets"),
        ("Indiana Pacers", "Indiana Pacers"),
        ("LA Clippers", "LA Clippers"),
        ("Los Angeles Lakers", "Los Angeles Lakers"),
        ("Memphis Grizzlies", "Memphis Grizzlies"),
        ("Miami Heat", "Miami Heat"),
        ("Milwaukee Bucks", "Milwaukee Bucks"),
        ("Minnesota Timberwolves", "Minnesota Timberwolves"),
        ("New Orleans Pelicans", "New Orleans Pelicans"),
        ("New York Knicks", "New York Knicks"),
        ("Oklahoma City Thunder", "Oklahoma City Thunder"),
        ("Orlando Magic", "Orlando Magic"),
        ("Philadelphia 76ers", "Philadelphia 76ers"),
        ("Phoenix Suns", "Phoenix Suns"),
        ("Portland Trail Blazers", "Portland Trail Blazers"),
        ("Sacramento Kings", "Sacramento Kings"),
        ("San Antonio Spurs", "San Antonio Spurs"),
        ("Toronto Raptors", "Toronto Raptors"),
        ("Utah Jazz", "Utah Jazz"),
        ("Washington Wizards", "Washington Wizards"),
        ("DONE✅", "done")
    ]

    for team_name, callback_data in teams:
        button = telebot.types.InlineKeyboardButton(text=team_name, callback_data=callback_data)
        markup.add(button)
    
    bot.send_message(message.chat.id, "Choose your NBA team:", reply_markup=markup)

# Callback to handle selected teams
@bot.callback_query_handler(func=lambda call: True)
def input_team(call):
    if call.data == 'done':
        bot.delete_message(call.message.chat.id, call.message.message_id)
    else:
        team_names.add(call.data)
        bot.send_message(call.message.chat.id, f"Team added: {call.data}. Monitoring for trailing alerts.")
        monitor_games(call.message.chat.id, team_names)

# Function to get spreads for NBA games from The Odds API
def get_nba_spreads():
    url = f'https://api.the-odds-api.com/v4/sports/basketball_nba/odds?regions=us&markets=spreads&apiKey={ODDS_API_KEY}'
    response = requests.get(url)
    if response.status_code == 200:
        return response.json()
    else:
        print("Error fetching spread data:", response.status_code)
        return None

# Function to get live scores for a specific team from API-NBA (Example placeholder)
def get_live_score(team_name, date):
    try:
        url = f'https://api-nba-v1.p.rapidapi.com/games?team={team_name}&date={date}'
        headers = {"Authorization": f"Bearer {API_NBA_KEY}"}
        response = requests.get(url, headers=headers)

        if response.status_code == 200:
            games = response.json().get('data', [])
            for game in games:
                if team_name.lower() in [game['home_team']['name'].lower(), game['away_team']['name'].lower()]:
                    return {
                        "home_team": game['home_team']['name'],
                        "away_team": game['away_team']['name'],
                        "home_score": game['home_team_score'],
                        "away_score": game['away_team_score'],
                    }
        else:
            print("Error fetching live score data:", response.status_code)
            return None
    except json.JSONDecodeError as e:
        print(f"JSON decode error: {e}.")
        return None

# Function to calculate the trailing margin based on live scores and the pre-game spread
def calculate_margin(team_name, pre_game_spread, date):
    live_game = get_live_score(team_name, date)
    if live_game:
        if team_name.lower() == live_game["home_team"].lower():
            trailing_margin = live_game["away_score"] - live_game["home_score"]
        else:
            trailing_margin = live_game["home_score"] - live_game["away_score"]
        return trailing_margin
    return None

# Monitor games and send alerts based on trailing margin
def monitor_games(chat_id, team_name_set):
    date = datetime.now().date().isoformat()
    spreads = get_nba_spreads()
    if spreads:
        for game in spreads:
            for team_name in team_name_set:
                if team_name.lower() in [game.get('home_team', '').lower(), game.get('away_team', '').lower()]:
                    try:
                        spread_info = game['bookmakers'][0]['markets'][0]['outcomes']
                        for outcome in spread_info:
                            if outcome['name'].lower() == team_name.lower():
                                pre_game_spread = float(outcome['point'])
                                alert_threshold = pre_game_spread + 10
                                trailing_margin = calculate_margin(team_name, pre_game_spread, date)
                                if trailing_margin is not None and trailing_margin > alert_threshold:
                                    bot.send_message(chat_id, f"Alert! {team_name} is trailing by more than {alert_threshold} points.")
                    except Exception as e:
                        print(f"Error accessing spread data for {team_name}: {e}")
    time.sleep(300)

# Webhook route to receive updates
@app.route('/webhook', methods=['POST'])
def webhook():
    if request.headers.get('content-type') == 'application/json':
        json_str = request.get_data().decode('UTF-8')
        update = telebot.types.Update.de_json(json_str)
        bot.process_new_updates([update])
        return "Webhook received", 200
    else:
        return "Unsupported Media Type", 415

# Route to set the webhook
@app.route('/set_webhook', methods=['GET'])
def set_webhook():
    webhook_url = 'https://your_domain.com/webhook'  # Replace with actual URL
    success = bot.set_webhook(url=webhook_url)
    return "Webhook setup successful" if success else "Webhook setup failed"

# Start Flask app
if __name__ == "__main__":
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 5000)))
