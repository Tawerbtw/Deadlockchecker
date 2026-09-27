from http.server import BaseHTTPRequestHandler, HTTPServer
import json
import time
import requests

PORT = 8000

LIVE_URL = "https://statlocker.gg/api/live/get-live-matches"

HISTORY_URL = (
    "https://statlocker.gg/api/profile/data/matches/"
    "{}/concise?limit=1&gameMode=1&matchMode=4&era=post&version=3"
)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 "
        "(KHTML, like Gecko) "
        "Chrome/140.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Referer": "https://statlocker.gg/",
    "Origin": "https://statlocker.gg",
}


# --------------------------------------------------
# Кэш
# --------------------------------------------------

live_cache = {
    "data": None,
    "time": 0
}

history_cache = {}

LIVE_CACHE_SECONDS = 10
HISTORY_CACHE_SECONDS = 120


# --------------------------------------------------
# Запросы к Statlocker
# --------------------------------------------------

def get_json(url):
    response = requests.get(
        url,
        headers=HEADERS,
        timeout=15
    )

    response.raise_for_status()

    return response.json()


def load_players():
    with open("players.json", "r", encoding="utf-8") as file:
        return json.load(file)


# --------------------------------------------------
# Live matches
# --------------------------------------------------

def get_live_matches():

    now = time.time()

    # Используем кэш 10 секунд
    if (
        live_cache["data"] is not None
        and now - live_cache["time"] < LIVE_CACHE_SECONDS
    ):
        return live_cache["data"]

    data = get_json(LIVE_URL)

    live_cache["data"] = data
    live_cache["time"] = now

    return data


# --------------------------------------------------
# Последний матч игрока
# --------------------------------------------------

def get_last_match(account_id):

    now = time.time()

    cached = history_cache.get(account_id)

    # Если история есть в кэше и ей меньше 2 минут
    if cached:
        if now - cached["time"] < HISTORY_CACHE_SECONDS:
            return cached["data"]

    try:

        url = HISTORY_URL.format(account_id)

        data = get_json(url)

        history = data.get("matchHistory", [])

        if not history:
            result = None
        else:

            match = history[0]

            result = {
                "matchId": match.get("match_id"),
                "startTime": match.get("start_time"),
                "durationS": match.get("match_duration_s"),
                "result": match.get("match_result")
            }

        history_cache[account_id] = {
            "data": result,
            "time": now
        }

        return result

    except Exception as error:

        print(
            f"History error for {account_id}: {error}"
        )

        # Если старый результат есть —
        # оставляем его
        if cached:
            return cached["data"]

        return None


# --------------------------------------------------
# Собираем игроков
# --------------------------------------------------

def get_players_status():

    players = load_players()

    live_matches = get_live_matches()

    # accountId -> информация о текущем матче
    active_players = {}

    for match in live_matches:

        for player in match.get("players", []):

            account_id = player.get("accountId")

            if account_id is None:
                continue

            steam_profile = player.get("steamProfile") or {}

            active_players[account_id] = {

                "matchId": match.get("matchId"),

                "durationS": match.get("durationS"),

                "gameMode": match.get("matchModeParsed"),

                "name": steam_profile.get("name"),

                "avatar": steam_profile.get("avatarUrl")
            }


    result = []


    for player in players:

        account_id = player["accountId"]

        current_match = active_players.get(account_id)


        # Игрок сейчас играет
        if current_match:

            result.append({

                "accountId": account_id,

                "name": (
                    current_match["name"]
                    or player["name"]
                ),

                "status": "in_game",

                "match": current_match,

                "lastMatch": get_last_match(account_id)
            })


        # Игрок сейчас не играет
        else:

            result.append({

                "accountId": account_id,

                "name": player["name"],

                "status": "not_in_game",

                "match": None,

                "lastMatch": get_last_match(account_id)
            })


    return result


# --------------------------------------------------
# HTTP сервер
# --------------------------------------------------

class Handler(BaseHTTPRequestHandler):

    def do_GET(self):

        if self.path.startswith("/api/players"):

            try:

                data = get_players_status()

                response = json.dumps(
                    data,
                    ensure_ascii=False
                ).encode("utf-8")


                self.send_response(200)

                self.send_header(
                    "Content-Type",
                    "application/json; charset=utf-8"
                )

                self.send_header(
                    "Cache-Control",
                    "no-cache"
                )

                self.end_headers()

                self.wfile.write(response)


            except Exception as error:

                print("API ERROR:", error)

                response = json.dumps(
                    {"error": str(error)},
                    ensure_ascii=False
                ).encode("utf-8")


                self.send_response(500)

                self.send_header(
                    "Content-Type",
                    "application/json; charset=utf-8"
                )

                self.end_headers()

                self.wfile.write(response)

            return


        if self.path == "/":

            try:

                with open(
                    "index.html",
                    "rb"
                ) as file:

                    content = file.read()


                self.send_response(200)

                self.send_header(
                    "Content-Type",
                    "text/html; charset=utf-8"
                )

                self.end_headers()

                self.wfile.write(content)


            except FileNotFoundError:

                self.send_response(404)

                self.end_headers()

            return


        self.send_response(404)

        self.end_headers()


print(
    f"Server started: http://localhost:{PORT}"
)

server = HTTPServer(
    ("localhost", PORT),
    Handler
)

server.serve_forever()