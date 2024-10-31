const TelegramBot = require('node-telegram-bot-api');
const axios = require('axios');
const dotenv = require('dotenv');
const dayjs = require('dayjs');

dotenv.config();

// Load API tokens from environment variables
const BOT_TOKEN = process.env.TELEGRAM_BOT_TOKEN;
const ODDS_API_KEY = process.env.ODDS_API_KEY;
const BALLDONTLIE_API_KEY = process.env.BALLDONTLIE;

const bot = new TelegramBot(BOT_TOKEN, { polling: true });
const alertMargin = 10;
let teamData = {};
let userTeams = {};

// Start command
bot.onText(/\/start/, (msg) => {
    bot.sendMessage(msg.chat.id, "Hello! I'll notify you if your NBA team is trailing by more than the set margin.");
    bot.sendMessage(msg.chat.id, "Please 👉🏾 /set_team to set up alerts.");
});

// Set team command with inline keyboard
bot.onText(/\/set_team/, (msg) => {
    const chatId = msg.chat.id;
    userTeams[chatId] = [];
    const teams = [
        'Atlanta Hawks','Boston Celtics','Brooklyn Nets','Charlotte Hornets','Chicago Bulls','Cleveland Cavaliers',
        'Dallas Mavericks','Denver Nuggets','Detroit Pistons','Golden State Warriors','Houston Rockets','Indiana Pacers','LA Clippers',
        'Los Angeles Lakers','Memphis Grizzlies','Miami Heat','Milwaukee Bucks','Minnesota Timberwolves','New Orleans Pelicans',
        'New York Knicks','Oklahoma City Thunder','Orlando Magic','Philadelphia 76ers','Phoenix Suns','Portland Trail Blazers',
        'Sacramento Kings','San Antonio Spurs','Toronto Raptors','Utah Jazz','Washington Wizards','DONE✅'
    ];
    
    const inlineKeyboard = teams.map(team => [{ text: team, callback_data: team }]);
    bot.sendMessage(chatId, "Choose your NBA team:", {
        reply_markup: { inline_keyboard: inlineKeyboard }
    });
});

// Callback handler for team selection
bot.on('callback_query', (callbackQuery) => {
    const chatId = callbackQuery.message.chat.id;
    const team = callbackQuery.data;
    
    if (team === 'DONE✅') {
        bot.editMessageReplyMarkup({ inline_keyboard: [] }, { chat_id: chatId, message_id: callbackQuery.message.message_id });
        const selectedTeams = userTeams[chatId].join(', ');
        bot.sendMessage(chatId, `Teams set to monitor: ${selectedTeams || 'None'}`);
        monitorGames(chatId, userTeams[chatId]);
    } else {
        if (!userTeams[chatId].includes(team)) {
            userTeams[chatId].push(team);
            bot.answerCallbackQuery(callbackQuery.id, { text: `${team} added to your list.` });
        }
    }
});



// Fetch spreads from Odds API
async function getNbaSpreads() {
    try {
        const url = `https://api.the-odds-api.com/v4/sports/basketball_nba/odds?regions=us&markets=spreads&apiKey=${ODDS_API_KEY}`;
        const response = await axios.get(url);
        return response.data;
    } catch (error) {
        console.error("Error fetching spread data:", error.response?.status);
        return null;
    }
}

// Fetch live score from BallDontLie
async function getLiveScore(teamName, date, chatId) {
    try {
        const teamsResponse = await axios.get('https://api.balldontlie.io/v1/teams', {
            headers: { "Authorization": BALLDONTLIE_API_KEY }
        });
        const teamData = teamsResponse.data.data.find(team => team.full_name.toLowerCase() === teamName.toLowerCase());
        if (!teamData) return null;

        const url = `https://api.balldontlie.io/v1/games?team_ids[]=${teamData.id}&start_date=${date}&end_date=${date}`;
        const response = await axios.get(url, { headers: { "Authorization": BALLDONTLIE_API_KEY } });
        const game = response.data.data[0];
        if (!game) {
            bot.sendMessage(chatId, `No games found for ${teamName} on ${date}.`);
            return null;
        }
        return {
            home_team: game.home_team.full_name,
            away_team: game.visitor_team.full_name,
            home_score: game.home_team_score,
            away_score: game.visitor_team_score,
        };
    } catch (error) {
        console.error("Error fetching live score data:", error.message);
        return null;
    }
}

// Calculate margin based on live score and spread
async function calculateMargin(teamName, preGameSpread, date, chatId) {
    const liveGame = await getLiveScore(teamName, date, chatId);
    if (!liveGame) return null;

    let trailingMargin;
    if (teamName.toLowerCase() === liveGame.home_team.toLowerCase()) {
        trailingMargin = liveGame.away_score - liveGame.home_score;
    } else {
        trailingMargin = liveGame.home_score - liveGame.away_score;
    }
    return trailingMargin;
}

// Check if a game is finished
async function isGameFinished(teamName, date) {
    try {
        
        const teamResponse = await axios.get('https://api.balldontlie.io/v1/teams',{
            headers: {
                Authorization: BALLDONTLIE_API_KEY },
        });
        
        const teams = teamResponse.data.data;
        const team = teams.find(t => t.full_name.toLowerCase() === teamName.toLowerCase());
        
        if (!team) {
            console.log(`Team ID not found for ${teamName}`);
            return { finished: false, message: `Team ID not found for ${teamName}` };
        }
        
        const gameResponse = await axios.get(`https://api.balldontlie.io/v1/games?team_ids[]=${team.id}&start_date=${date}&end_date=${date}`);
        
        const games = gameResponse.data.data;
        const game = games.find(g => g.status.toLowerCase() === "final");
        
        if (game) {
            return { finished: true, message: `${teamName}'s game has finished.` };
        } else if (games.length > 0) {
            return { finished: false, message: `${teamName}'s game is not yet started or still in progress.` };
        } else {
            return { finished: false, message: "No game information found for today." };
        }
    } catch (error) {
        console.error("Error fetching game status:", error);
        return { finished: false, message: "Error fetching game data." };
    }
}


// Monitor games and alert if margin exceeds threshold
/*async function monitorGames(chatId, teamNames) {
    const date = dayjs().format('YYYY-MM-DD');
    const spreads = await getNbaSpreads();
    if (!spreads) return;

    for (const teamName of teamNames) {
        const game = spreads.find(g => 
            [g.home_team, g.away_team].some(team => team.toLowerCase() === teamName.toLowerCase())
        );
        if (game) {
            const spreadData = game.bookmakers.find(b => b.title === 'FanDuel') || game.bookmakers[0];
            const preGameSpread = spreadData.markets[0].outcomes.find(o => o.name.toLowerCase() === teamName.toLowerCase())?.point;
            if (preGameSpread !== undefined) {
                teamData[teamName] = { preGameSpread, alert_threshold: preGameSpread + alertMargin };
                bot.sendMessage(chatId, `Pre-game spread for ${teamName}: ${preGameSpread}.\nAlert threshold: ${preGameSpread + alertMargin}.`);

                const trailingMargin = await calculateMargin(teamName, preGameSpread, date, chatId);
                if (trailingMargin > teamData[teamName].alert_threshold) {
                    bot.sendMessage(chatId, `Alert! ${teamName} is trailing by more than ${teamData[teamName].alert_threshold} points.`);
                }

                if (await isGameFinished(teamName, date)) {
                    delete teamData[teamName];
                }
            }
        }
    }
    setTimeout(() => monitorGames(chatId, teamNames), 300000); // Repeat every 5 minutes
}*/
async function monitorGames(chatId, teamNames) {
    const date = dayjs().format('YYYY-MM-DD');
    const spreads = await getNbaSpreads();

    if (!spreads) {
        console.error("No spread data available from Odds API.");
        return;
    }

    for (const teamName of teamNames) {
        const game = spreads.find(g => 
            [g.home_team, g.away_team].some(team => team.toLowerCase() === teamName.toLowerCase())
        );

        if (!game) {
            console.error(`Spread data not found for ${teamName}.`);
            bot.sendMessage(chatId, `<i>Spread data unavailable for ${teamName}.</i>`, { parse_mode: 'HTML' });
            continue;  // Skip to the next team if no spread data
        }

        const spreadData = game.bookmakers.find(b => b.title === 'FanDuel') || game.bookmakers[0];
        const preGameSpread = spreadData.markets[0]?.outcomes.find(o => o.name.toLowerCase() === teamName.toLowerCase())?.point;

        if (preGameSpread === undefined) {
            console.error(`Pre-game spread not found for ${teamName}.`);
            bot.sendMessage(chatId, `<i>Pre-game spread data unavailable for ${teamName}.</i>`, { parse_mode: 'HTML' });
            continue;  // Skip to the next team if no pre-game spread
        }

        teamData[teamName] = { preGameSpread, alert_threshold: preGameSpread + alertMargin };
        bot.sendMessage(chatId, `<b>Pre-game spread for ${teamName}: ${preGameSpread}\nAlert threshold: ${preGameSpread + alertMargin}</b>`,{ parse_mode: 'HTML' });

        const trailingMargin = await calculateMargin(teamName, preGameSpread, date, chatId);

        if (trailingMargin === null) {
            console.error(`Unable to calculate margin for ${teamName} due to missing live score data.`);
            bot.sendMessage(chatId, `<i>Live score data unavailable for ${teamName}.</i>`, { parse_mode: 'HTML' });
            continue;  // Skip to the next team if margin couldn't be calculated
        }

        // Send alert if margin exceeds threshold
        if (trailingMargin > teamData[teamName].alert_threshold) {
            bot.sendMessage(chatId, `<b>Alert! ${teamName} is trailing by more than ${teamData[teamName].alert_threshold} points.</b>`, { parse_mode: 'HTML' });
        }

        // Check if game is finished and remove from tracking if it is
        const gameFinished = await isGameFinished(teamName, date);
        if (gameFinished.finished) {
            bot.sendMessage(chatId, gameFinished.message);
            delete teamData[teamName];
        }
    }
    
    setTimeout(() => monitorGames(chatId, teamNames), 300000); // Repeat every 5 minutes
}


console.log("Bot is running...");
