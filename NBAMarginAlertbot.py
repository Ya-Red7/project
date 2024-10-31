'''import os
import telebot
import requests
import time
from datetime import datetime
from dotenv import load_dotenv
from flask import Flask, request
import logging

load_dotenv()

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
ODDS_API_KEY = os.getenv("ODDS_API_KEY")
BALLDONTLIE_API_KEY = os.getenv("BALLDONTLIE")
team_data = {}
bot = telebot.TeleBot(BOT_TOKEN)
alert_margin = 10
user_teams = {}

@bot.message_handler(commands=['start'])
def start(message):
    bot.reply_to(message, "Hello! I'll notify you if your NBA team is trailing by more than the set margin.")
    bot.reply_to(message, "Please 👉🏾 /set_team to set up alerts.")

@bot.message_handler(commands=['set_team'])
def set_team(message):
    markup = telebot.types.InlineKeyboardMarkup(row_width=5)
    teams = [
        ("Atlanta Hawks", "Atlanta Hawks"), ("Boston Celtics", "Boston Celtics"),
        ("Brooklyn Nets", "Brooklyn Nets"), ("Charlotte Hornets", "Charlotte Hornets"),
        ("Chicago Bulls", "Chicago Bulls"), ("Cleveland Cavaliers", "Cleveland Cavaliers"),
        ("Dallas Mavericks", "Dallas Mavericks"), ("Denver Nuggets", "Denver Nuggets"),
        ("Detroit Pistons", "Detroit Pistons"), ("Golden State Warriors", "Golden State Warriors"),
        ("Houston Rockets", "Houston Rockets"), ("Indiana Pacers", "Indiana Pacers"),
        ("Los Angeles Clippers", "Los Angeles Clippers"), ("Los Angeles Lakers", "Los Angeles Lakers"),
        ("Memphis Grizzlies", "Memphis Grizzlies"), ("Miami Heat", "Miami Heat"),
        ("Milwaukee Bucks", "Milwaukee Bucks"), ("Minnesota Timberwolves", "Minnesota Timberwolves"),
        ("New Orleans Pelicans", "New Orleans Pelicans"), ("New York Knicks", "New York Knicks"),
        ("Oklahoma City Thunder", "Oklahoma City Thunder"), ("Orlando Magic", "Orlando Magic"),
        ("Philadelphia 76ers", "Philadelphia 76ers"), ("Phoenix Suns", "Phoenix Suns"),
        ("Portland Trail Blazers", "Portland Trail Blazers"), ("Sacramento Kings", "Sacramento Kings"),
        ("San Antonio Spurs", "San Antonio Spurs"), ("Toronto Raptors", "Toronto Raptors"),
        ("Utah Jazz", "Utah Jazz"), ("Washington Wizards", "Washington Wizards"),
        ("DONE✅", "done")
    ]
    for team_name, callback_data in teams:
        button = telebot.types.InlineKeyboardButton(text=team_name, callback_data=callback_data)
        markup.add(button)
    bot.send_message(message.chat.id, "Choose your NBA team:", reply_markup=markup)
    user_teams[message.chat.id] = []

@bot.callback_query_handler(func=lambda call: True)
def input_team(call):
    chat_id = call.message.chat.id
    if call.data == 'done':
        bot.delete_message(chat_id, call.message.message_id)
        selected_teams = user_teams.get(chat_id, [])
        if selected_teams:
            bot.send_message(chat_id, f"Teams set to monitor: {', '.join(selected_teams)}.")
        else:
            bot.send_message(chat_id, "Teams set to monitor: None.")
        monitor_games(chat_id, selected_teams)
    else:
        if call.data not in user_teams[chat_id]:
            user_teams[chat_id].append(call.data)
            bot.answer_callback_query(call.id, f"{call.data} added to your list.")

def get_nba_spreads():
    odds_url = f"https://api.the-odds-api.com/v4/sports/basketball_nba/odds/?apiKey={ODDS_API_KEY}&regions=us&markets=spreads"
    response = requests.get(odds_url)
    spreads = {}
    if response.status_code == 200:
        data = response.json()
        for game in data:
            home_team = game["home_team"]
            away_team = game["away_team"]
            odds = game["bookmakers"][0]["markets"][0]["outcomes"]
            home_spread = next((outcome["point"] for outcome in odds if outcome["name"] == home_team), None)
            spreads[home_team] = home_spread
            spreads[away_team] = -home_spread
    return spreads

def get_live_score(team_name, date, userid):
    url = f"https://www.balldontlie.io/api/v1/games?start_date={date}&end_date={date}&team_ids[]={team_data[team_name]}&postseason=false"
    response = requests.get(url)
    if response.status_code == 200:
        data = response.json()
        for game in data['data']:
            home_team = game['home_team']['full_name']
            away_team = game['visitor_team']['full_name']
            if team_name == home_team:
                return game['home_team_score'] - game['visitor_team_score']
            elif team_name == away_team:
                return game['visitor_team_score'] - game['home_team_score']
    return None

def calculate_margin(team_name, pre_game_spread, date, userid):
    margin = get_live_score(team_name, date, userid)
    if margin is not None:
        if margin < pre_game_spread - alert_margin:
            bot.send_message(userid, f"Alert: {team_name} is trailing by more than {alert_margin} points!")
    return margin

def is_game_finished(team_name, date):
    url = f"https://www.balldontlie.io/api/v1/games?start_date={date}&end_date={date}&team_ids[]={team_data[team_name]}&postseason=false"
    response = requests.get(url)
    if response.status_code == 200:
        data = response.json()
        for game in data['data']:
            if game['status'] == "Final":
                return True
    return False

def monitor_games(chat_id, team_names):
    date_today = datetime.now().strftime("%Y-%m-%d")
    spreads = get_nba_spreads()
    for team_name in team_names:
        pre_game_spread = spreads.get(team_name)
        if pre_game_spread is not None:
            while not is_game_finished(team_name, date_today):
                calculate_margin(team_name, pre_game_spread, date_today, chat_id)
                time.sleep(30)

app = Flask(__name__)

@app.route(f'/{BOT_TOKEN}', methods=['POST'])
def webhook():
    update = telebot.types.Update.de_json(request.get_json(force=True))
    bot.process_new_updates([update])
    return 'OK', 200

@app.route('/set_webhook', methods=['GET', 'POST'])
def set_webhook():
    webhook_url = f"https://project-9e2j.onrender.com/{BOT_TOKEN}"
    success = bot.set_webhook(url=webhook_url)
    return 'Webhook setup' if success else 'Webhook setup failed', 200

if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG, format='%(asctime)s %(message)s')
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
'''