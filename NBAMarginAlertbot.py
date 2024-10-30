import os
import telebot
import requests
import time
from datetime import datetime
from dotenv import load_dotenv
import json
from flask import Flask, request
from waitress import serve
import logging

load_dotenv()

# Get API tokens from environment variables
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
ODDS_API_KEY = os.getenv("ODDS_API_KEY")
BALLDONTLIE_API_KEY = os.getenv("BALLDONTLIE")
team_names = []
team_data = {}
bot = telebot.TeleBot(BOT_TOKEN)
alert_margin = 10

logging.basicConfig(level=logging.DEBUG, format='%(asctime)s %(message)s')
app = Flask(__name__)

# User teams dictionary to store selected teams by user
user_teams = {}

# Start Command
@bot.message_handler(commands=['start'])
def start(message):
    bot.reply_to(message, "Hello! I'll notify you if your NBA team is trailing by more than the set margin.")
    bot.reply_to(message, "Please 👉🏾 /set_team to set up alerts.")

# Set team command with InlineKeyboard
@bot.message_handler(commands=['set_team'])
def set_team(message):
    markup = telebot.types.InlineKeyboardMarkup(row_width=5)
    teams = [("Atlanta Hawks", "Atlanta Hawks"), ("Boston Celtics", "Boston Celtics"), # add other teams
             ("DONE✅", "done")]
    for team_name, callback_data in teams:
        markup.add(telebot.types.InlineKeyboardButton(text=team_name, callback_data=callback_data))
    bot.send_message(message.chat.id, "Choose your NBA team:", reply_markup=markup)
    user_teams[message.chat.id] = []  # Initialize list for user teams

@bot.callback_query_handler(func=lambda call: True)
def input_team(call):
    chat_id = call.message.chat.id
    if call.data == 'done':
        bot.delete_message(chat_id, call.message.message_id)
        selected_teams = user_teams.get(chat_id, [])
        bot.send_message(chat_id, f"Teams set to monitor: {', '.join(selected_teams) if selected_teams else 'None'}.")
        monitor_games(chat_id, selected_teams)  # Call monitor_games to start monitoring
    else:
        if call.data not in user_teams[chat_id]:
            user_teams[chat_id].append(call.data)
            bot.answer_callback_query(call.id, f"{call.data} added to your list.")

# Fetch NBA spreads from The Odds API
def get_nba_spreads():
    url = f'https://api.the-odds-api.com/v4/sports/basketball_nba/odds?regions=us&markets=spreads&apiKey={ODDS_API_KEY}'
    response = requests.get(url)
    return response.json() if response.status_code == 200 else None

# Fetch live score from BallDontLie
def get_live_score(team_name, date, userid):
    try:
        teams_response = requests.get('https://api.balldontlie.io/v1/teams', headers={"Authorization": BALLDONTLIE_API_KEY})
        team_id = next((team['id'] for team in teams_response.json().get('data', []) if team['full_name'].lower() == team_name.lower()), None)
        if not team_id:
            return None
        url = f'https://api.balldontlie.io/v1/games?team_ids[]={team_id}&start_date={date}&end_date={date}'
        response = requests.get(url, headers={"Authorization": BALLDONTLIE_API_KEY})
        games = response.json().get('data', [])
        for game in games:
            return {"home_team": game['home_team']['full_name'], "away_team": game['visitor_team']['full_name'],
                    "home_score": game['home_team_score'], "away_score": game['visitor_team_score']}
    except (json.JSONDecodeError, requests.RequestException) as e:
        return None

# Calculate trailing margin
def calculate_margin(team_name, pre_game_spread, date, userid):
    live_game = get_live_score(team_name, date, userid)
    if live_game:
        trailing_margin = live_game["away_score"] - live_game["home_score"] if team_name.lower() == live_game["home_team"].lower() else live_game["home_score"] - live_game["away_score"]
        return trailing_margin
    return None

# Check if game is finished
def is_game_finished(team_name, date):
    try:
        teams_response = requests.get('https://api.balldontlie.io/v1/teams', headers={"Authorization": BALLDONTLIE_API_KEY})
        team_id = next((team['id'] for team in teams_response.json().get('data', []) if team['full_name'].lower() == team_name.lower()), None)
        if not team_id:
            return False
        url = f'https://api.balldontlie.io/v1/games?team_ids[]={team_id}&start_date={date}&end_date={date}'
        response = requests.get(url, headers={"Authorization": BALLDONTLIE_API_KEY})
        for game in response.json().get('data', []):
            if game.get('status') == "Final":
                return True
    except requests.RequestException:
        return False
    return False

# Monitor games for selected teams
def monitor_games(chat_id, team_names):
    global team_data
    while True:
        date = datetime.now().date().isoformat()
        spreads = get_nba_spreads()
        if spreads:
            for team_name in team_names:
                for game in spreads:
                    if team_name.lower() in [game.get('home_team', '').lower(), game.get('away_team', '').lower()]:
                        try:
                            fanduel_data = next((bookmaker for bookmaker in game['bookmakers'] if bookmaker['title'] == 'FanDuel'), game['bookmakers'][0])
                            spread_info = fanduel_data['markets'][0]['outcomes']
                            pre_game_spread = float(next(outcome['point'] for outcome in spread_info if outcome['name'].lower() == team_name.lower()))
                            if team_name not in team_data:
                                team_data[team_name] = {'pre_game_spread': pre_game_spread, 'alert_threshold': pre_game_spread + 10}
                            trailing_margin = calculate_margin(team_name, pre_game_spread, date, chat_id)
                            if trailing_margin and trailing_margin > team_data[team_name]['alert_threshold']:
                                bot.send_message(chat_id, f"Alert! {team_name} is trailing by more than the threshold of {team_data[team_name]['alert_threshold']} points.")
                            if is_game_finished(team_name, date):
                                del team_data[team_name]
                        except (KeyError, ValueError):
                            pass
        time.sleep(300)

# Webhook Route
@app.route(f'/{BOT_TOKEN}', methods=['POST'])
def webhook():
    update = telebot.types.Update.de_json(request.get_json(force=True))
    bot.process_new_updates([update])
    return 'OK', 200

# Set Webhook Route
@app.route('/set_webhook', methods=['GET', 'POST'])
def set_webhook():
    webhook_url = f"https://api.telegram.org/bot{BOT_TOKEN}/setWebhook?url=https://project-9e2j.onrender.com/{BOT_TOKEN}"
    success = bot.set_webhook(url=webhook_url)
    return 'Webhook setup' if success else 'Webhook setup failed', 200

if __name__ == "__main__":
    serve(app, host='0.0.0.0', port=5000)
