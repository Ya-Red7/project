from flask import Flask, request
#from gevent.pywsgi import WSGIServer
from waitress import serve
import logging
from NBAMarginAlertbot import bot,BOT_TOKEN
import telebot
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s %(message)s')

app = Flask(__name__)

# Define a route for webhook updates
@app.route(f'/{BOT_TOKEN}', methods=['POST'])
def webhook():
    update = telebot.types.Update.de_json(request.get_json(force=True))
    bot.process_new_updates([update])
    return 'OK', 200

# Example of setting the webhook
@app.route('/set_webhook', methods=['GET', 'POST'])
def set_webhook():
    #webhook_url = f"https://project-9e2j.onrender.com/{BOT_TOKEN}"  # Replace <YOUR_RENDER_APP_URL> with Render URL
    webhook_url = f"https://api.telegram.org/bot{BOT_TOKEN}/setWebhook?url=https://project-9e2j.onrender.com/{BOT_TOKEN}"  # Replace <YOUR_RENDER_APP_URL> with Render URL
    success = bot.set_webhook(url=webhook_url)
    return 'Webhook setup' if success else 'Webhook setup failed', 200


if __name__ == "__main__":
    #app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
    
    serve(app, host='0.0.0.0', port=5000)
    #http_server = WSGIServer(('', 5000), app)
    #http_server.serve_forever()