from http.server import BaseHTTPRequestHandler, HTTPServer
import json
import time
import copy
from time import sleep
import random
import threading
from enum import Enum
from urllib.parse import urlparse, parse_qs
import platform
import os

URL = '0.0.0.0'
is_server = platform.system() == "Linux"

if not is_server:
  URL = 'localhost'
server_address = (URL, 25560)

class TgtHiderType(Enum):
  JAK = 0
  ORB = 1
  # SAMOS = 2

class HnsLevelMode(Enum):
  FULL_GAME = 0
  HUB1 = 1
  HUB2 = 2
  HUB3 = 3
  TRAINING = 4
  VILLAGE1 = 5
  BEACH = 6
  JUNGLE = 7
  MISTY = 8
  FIRECANYON = 9
  VILLAGE2 = 10
  SUNKEN = 11
  SWAMP = 12
  ROLLING = 13
  OGRE = 14
  VILLAGE3 = 15
  SNOW = 16
  CAVE = 17
  LAVATUBE = 18
  CITADEL = 19

class ContPtMode(Enum):
  DIFFERENT = 0
  SAME = 1  # not yet supported

class MpGameRole(Enum):
  LOBBY = 0
  HIDER = 1
  SEEKER = 2
  FOUND = 3

class MpGameState(Enum):
  INVALID = 0
  LOBBY = 1
  STARTING_SOON = 2
  PLAY_HIDE = 3
  PLAY_SEEK = 4
  END = 5

class MpTargetState(Enum):
  INVALID = 0
  LOBBY = 1
  READY = 2
  START = 3
  HIDER_START = 4
  HIDER_PLAY = 5
  HIDER_FOUND = 6
  SEEKER_WAIT = 7
  SEEKER_START = 8
  SEEKER_PLAY = 9

DEFAULT_MP_INFO = {
  "state": MpGameState.INVALID.value,
  "target_hider_type": TgtHiderType.JAK.value,
  "level_mode": HnsLevelMode.FULL_GAME.value,
  "continue_point_mode": ContPtMode.DIFFERENT.value,
  "hiders_move": 1,
  "hiders_pause_zoom": 1,
  "seekers_infect": 0,
  "num_seekers": 1, # default to one seeker
  "last_winner_as_seeker": 1,
  "fog_distance": 0.0,
  "hider_speed": 1.0,
  "seeker_speed": 1.0,
  "time_to_start": 10,
  "time_to_hide": 30,
  "hider_victory_timeout": 300,
  "post_game_timeout": 15,
  "alert_found_pnum": -1,
  "alert_seeker_pnum": -1,
  "num_hiders": -1,
  "num_hiders_left": -1
}
MP_INFO = copy.deepcopy(DEFAULT_MP_INFO)
PLAYER_IDX_LOOKUP = {}
PLAYER_LIST = []
DEFAULT_PLAYER_INFO = {
  "is_admin": 0,
  "role": MpGameRole.LOBBY.value,
  "collected_by_pnum": -1,
  "rank": -1,
  "mp_state": MpTargetState.INVALID.value,
  "last_update": 0
}

# PLAYER_DISCONNECT_TIMEOUT = 600 # 10 min for development/testing
PLAYER_DISCONNECT_TIMEOUT = 30 # 30 sec for real use

def get_banned_ips():
    banned_ips = []
    if os.path.exists('banned_ips.txt'):
        print("FOUND BANNED IP FILE")
        with open('banned_ips.txt', 'r') as f:
            for line in f:
                banned_ips.append(line.strip())
    return banned_ips

def determine_admin_player():
  total_players = 0
  for i in range(len(PLAYER_LIST)):
    if PLAYER_LIST[i] is None or PLAYER_LIST[i] == {} or "mp_state" not in PLAYER_LIST[i] or MpTargetState(PLAYER_LIST[i]["mp_state"]) == MpTargetState.INVALID:
      PLAYER_LIST[i]["is_admin"] = 0
      # dont count this player as joined
      continue

    total_players += 1
    if total_players == 1:
      PLAYER_LIST[i]["is_admin"] = 1
    else:
      PLAYER_LIST[i]["is_admin"] = 0

class RequestHandler(BaseHTTPRequestHandler):
  def send_response_bad_request_400(self):
    self.send_response(400)
    self.send_header('Content-type', 'application/json')
    self.end_headers()
    self.wfile.write(bytes("400 Bad Request", "UTF-8"))
    self.wfile.flush()

  def send_response_not_found_404(self):
    self.send_response(404)
    self.send_header('Content-type', 'text/html')
    self.end_headers()
    self.wfile.write(bytes("404 Not Found", "UTF-8"))
    self.wfile.flush()
  
  def do_GET(self):
    url = urlparse(self.path)

    # Extract parameters from the query string
    query = parse_qs(url.query)

    # routing
    match url.path:

      # get 
      case "/get":
        response_data = {
          "game_state": MP_INFO["state"],
          "target_hider_type": MP_INFO["target_hider_type"],
          "level_mode": MP_INFO["level_mode"],
          "continue_point_mode": MP_INFO["continue_point_mode"],
          "hiders_move": MP_INFO["hiders_move"],
          "hiders_pause_zoom": MP_INFO["hiders_pause_zoom"],
          "seekers_infect": MP_INFO["seekers_infect"],
          "num_seekers": MP_INFO["num_seekers"],
          "last_winner_as_seeker": MP_INFO["last_winner_as_seeker"],
          "fog_distance": MP_INFO["fog_distance"],
          "hider_speed": MP_INFO["hider_speed"],
          "seeker_speed": MP_INFO["seeker_speed"],
          "time_to_start": MP_INFO["time_to_start"],
          "time_to_hide": MP_INFO["time_to_hide"],
          "hider_victory_timeout": MP_INFO["hider_victory_timeout"],
          "post_game_timeout": MP_INFO["post_game_timeout"],
          "alert_found_pnum": MP_INFO["alert_found_pnum"],
          "alert_seeker_pnum": MP_INFO["alert_seeker_pnum"],
          "num_hiders": MP_INFO["num_hiders"],      
          "num_hiders_left": MP_INFO["num_hiders_left"],
          "players": {}
        }
        for i in range(len(PLAYER_LIST)):
          response_data["players"][i] = PLAYER_LIST[i]

        # Return JSON response
        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.end_headers()

        # Convert the dictionary to JSON format
        json_data = json.dumps(response_data)
        # Write JSON data to the response body
        self.wfile.write(json_data.encode())
        self.wfile.flush()

      # else unknown path
      case _:
        self.send_response_not_found_404()

  def do_POST(self):
    # Get content length
    content_length = int(self.headers['Content-Length'])

    url = urlparse(self.path)

    # Extract parameters from the query string
    query = parse_qs(url.query)

    # routing
    match url.path:
      # clear
      case "/clear":
        PLAYER_LIST.clear()
        PLAYER_IDX_LOOKUP.clear()
        for k in DEFAULT_MP_INFO:
          MP_INFO[k] = DEFAULT_MP_INFO[k]

        # Send response status code
        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.end_headers()
        self.wfile.flush()

      # register
      case "/register":
        username = query.get('username', [])
        ip = self.client_address[0]  # Get client IP address

        if len(PLAYER_LIST) == 0:
          # first player, setup lobby
          MP_INFO["state"] = MpGameState.LOBBY.value

        if len(username) == 0 or len(username[0]) == 0:
          self.send_response_bad_request_400()
        elif ip in get_banned_ips():
          # IP is banned, send 403 Forbidden status
          self.send_response(403)
          self.send_header('Content-type', 'text/plain')
          self.end_headers()
          self.wfile.write(b"Your IP address has been banned.")
          self.wfile.flush()
        else:
          if username[0] in PLAYER_IDX_LOOKUP:
            # existing user, treat as rejoin
            player_num = PLAYER_IDX_LOOKUP[username[0]]
          else:
            # new user
            player_num = len(PLAYER_LIST)  # TODO: loop to find next open slot (after dropping players)
            PLAYER_IDX_LOOKUP[username[0]] = player_num

            # fill out empty keys
            player_info = copy.deepcopy(DEFAULT_PLAYER_INFO)
            player_info["mp_state"] = MpTargetState.LOBBY.value
            player_info["last_update"] = time.time()
            PLAYER_LIST.append(player_info)

          determine_admin_player()

          self.send_response(200)
          self.send_header('Content-type', 'application/json')
          self.end_headers()
          
          response_data = {
            "game_state": MP_INFO["state"],
            "player_num": player_num,
            "is_admin": PLAYER_LIST[player_num]["is_admin"]
          }

          json_data = json.dumps(response_data)
          # Write JSON data to the response body
          self.wfile.write(json_data.encode())
          self.wfile.flush()

      # update (player updating themselves)
      case "/update":
        username = query.get('username', [])

        if len(username) == 0 or len(username[0]) == 0 or not username[0] in PLAYER_IDX_LOOKUP:
          # unknown player
          self.send_response_bad_request_400()
        else:
          player_num = PLAYER_IDX_LOOKUP[username[0]]
          # Get raw body data
          raw_data = self.rfile.read(content_length)
          # Parse JSON data into dictionary
          data = json.loads(raw_data.decode('utf-8'))
        
          for k in data:
            PLAYER_LIST[player_num][k] = data[k]
          PLAYER_LIST[player_num]["last_update"] = time.time()
      
          # Send response status code
          self.send_response(200)
          self.send_header('Content-type', 'application/json')
          self.end_headers()
          self.wfile.flush()

      # settings update, should only be done by admin
      case "/update_settings":
        username = query.get('username', [])

        if len(username) == 0 or len(username[0]) == 0 or not username[0] in PLAYER_IDX_LOOKUP:
          # unknown player
          self.send_response_bad_request_400()
        else:
          player_num = PLAYER_IDX_LOOKUP[username[0]]

          # only respect update from admins
          if PLAYER_LIST[player_num]["is_admin"] == 1:
            # Get raw body data
            raw_data = self.rfile.read(content_length)
            # Parse JSON data into dictionary
            data = json.loads(raw_data.decode('utf-8'))
          
            for k in data:
              MP_INFO[k] = data[k]
      
          # Send response status code
          self.send_response(200)
          self.send_header('Content-type', 'application/json')
          self.end_headers()
          self.wfile.flush()
      
      case "/mark_found":
        # Get raw body data
        raw_data = self.rfile.read(content_length)
        # Parse JSON data into dictionary
        data = json.loads(raw_data.decode('utf-8'))
      
        seeker = data["seeker_username"]
        found = data["found_username"]

        if seeker in PLAYER_IDX_LOOKUP and found in PLAYER_IDX_LOOKUP:
          # if MP_INFO["seekers_infect"] == 1:
          #   PLAYER_LIST[PLAYER_IDX_LOOKUP[found]]["role"] = MpGameRole.SEEKER.value
          # else:
          PLAYER_LIST[PLAYER_IDX_LOOKUP[found]]["role"] = MpGameRole.FOUND.value
          PLAYER_LIST[PLAYER_IDX_LOOKUP[found]]["collected_by_pnum"] = PLAYER_IDX_LOOKUP[seeker]
          MP_INFO["alert_found_pnum"] = PLAYER_IDX_LOOKUP[found]
          MP_INFO["alert_seeker_pnum"] = PLAYER_IDX_LOOKUP[seeker]
          MP_INFO["num_hiders_left"] -= 1
          PLAYER_LIST[PLAYER_IDX_LOOKUP[found]]["rank"] = MP_INFO["num_hiders_left"] + MP_INFO["num_seekers"]
        else:
          print("couldn't find player(s) in mark_found", hider, seeker)
    
        # Send response status code
        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.end_headers()
        self.wfile.flush()

      # else unknown path
      case _:
        self.send_response_not_found_404()
       
def game_loop():
  last_state_change_time = time.time()  # seconds
  latest_alert_time = 0 # seconds
  while True:
    # dont be CPU hog
    sleep(0.01)

    # nobody connected, nothing to do
    if "state" not in MP_INFO.keys() or MP_INFO["state"] == MpGameState.INVALID.value:
      continue

    # players found alert
    if latest_alert_time == 0 and MP_INFO["alert_found_pnum"] >= 0 and MP_INFO["alert_seeker_pnum"] >= 0:
      latest_alert_time = time.time()
    # dismiss after 5s
    elif latest_alert_time > 0 and (time.time() - latest_alert_time) > 5:
      latest_alert_time = 0
      MP_INFO["alert_found_pnum"] = -1 
      MP_INFO["alert_seeker_pnum"] = -1

    # collect some info
    admin_start = False
    total_players = 0
    player_counts = {
      MpTargetState.LOBBY: 0,
      MpTargetState.READY: 0,
      MpTargetState.START: 0,
      MpTargetState.HIDER_START: 0,
      MpTargetState.HIDER_PLAY: 0,
      MpTargetState.HIDER_FOUND: 0,
      MpTargetState.SEEKER_WAIT: 0,
      MpTargetState.SEEKER_START: 0,
      MpTargetState.SEEKER_PLAY: 0
    }

    determine_admin_player()

    for i in range(len(PLAYER_LIST)):

      if PLAYER_LIST[i] is None or PLAYER_LIST[i] == {} or "mp_state" not in PLAYER_LIST[i] or MpTargetState(PLAYER_LIST[i]["mp_state"]) == MpTargetState.INVALID:
        PLAYER_LIST[i]["is_admin"] = 0
        # dont count this player as joined
        continue
      
      if "last_update" in PLAYER_LIST[i] and PLAYER_LIST[i]["last_update"] > 0 and time.time() - PLAYER_LIST[i]["last_update"] >= PLAYER_DISCONNECT_TIMEOUT:
        print(f"player {i} hasn't updated in {PLAYER_DISCONNECT_TIMEOUT}s, removing them")
        # havent heard from player in too long, kick them out
        if "username" in PLAYER_LIST[i] and PLAYER_LIST[i]["username"] in PLAYER_IDX_LOOKUP:
          PLAYER_IDX_LOOKUP.pop(PLAYER_LIST[i]["username"]) 
        PLAYER_LIST[i] = copy.deepcopy(DEFAULT_PLAYER_INFO)
        continue

      total_players += 1
      state = MpTargetState(PLAYER_LIST[i]["mp_state"])
      if state not in player_counts:
        player_counts[state] = 0
      player_counts[state] += 1

      match state:
        case MpTargetState.START:
          if PLAYER_LIST[i]["is_admin"] == 1:
            admin_start = True

    # update state conditionally
    match MP_INFO["state"]:
      case MpGameState.LOBBY.value:
        # reset player data
        for i in range(len(PLAYER_LIST)):
          PLAYER_LIST[i]["role"] = MpGameRole.LOBBY.value
          PLAYER_LIST[i]["collected_by_pnum"] = -1
          PLAYER_LIST[i]["rank"] = -1
        # go to STARTING_SOON if either:
        # - an admin wants to start
        # - 50% are ready/start and anyone wants to start
        if admin_start or (player_counts[MpTargetState.START] > 0 and (player_counts[MpTargetState.READY] + player_counts[MpTargetState.START]) * 2 >= total_players):
          print("LOBBY -> STARTING_SOON")
          MP_INFO["state"] = MpGameState.STARTING_SOON.value
          last_state_change_time = time.time()
      case MpGameState.STARTING_SOON.value:
        # see if timer is up and we should begin hiding
        if time.time() - last_state_change_time >= MP_INFO["time_to_start"]:
          print("starting game, assigning roles")

          players = 0
          for i in range(len(PLAYER_LIST)):
            if PLAYER_LIST[i] is not None and PLAYER_LIST[i] != {} and (PLAYER_LIST[i]["mp_state"] == MpTargetState.READY.value or PLAYER_LIST[i]["mp_state"] == MpTargetState.START.value or PLAYER_LIST[i]["role"] == MpGameRole.LOBBY.value):
              players += 1

          # potentially adjust num seekers based on num players (should always be at least one hider)
          MP_INFO["num_seekers"] = min(MP_INFO["num_seekers"], players-1)

          # assign seekers randomly
          seekers = 0
          while seekers < MP_INFO["num_seekers"]:
            i = random.randrange(len(PLAYER_LIST))
            
            if (PLAYER_LIST[i] is None or PLAYER_LIST[i] == {} or
                # skip players who weren't in start state
                (PLAYER_LIST[i]["mp_state"] != MpTargetState.READY.value and PLAYER_LIST[i]["mp_state"] != MpTargetState.START.value) or
                # skip players who were already assigned SEEKER
                PLAYER_LIST[i]["role"] != MpGameRole.LOBBY.value):
              continue
            print(f"player {i} is seeker")
            PLAYER_LIST[i]["role"] = MpGameRole.SEEKER.value
            seekers += 1

          hiders = 0
          # set remaining players to HIDER
          for i in range(len(PLAYER_LIST)):
            if (PLAYER_LIST[i] is None or PLAYER_LIST[i] == {} or
                # skip players who weren't in start state
                (PLAYER_LIST[i]["mp_state"] != MpTargetState.READY.value and PLAYER_LIST[i]["mp_state"] != MpTargetState.START.value) or
                # skip players who were already assigned SEEKER
                PLAYER_LIST[i]["role"] != MpGameRole.LOBBY.value):
              continue
            print(f"player {i} is hider")
            PLAYER_LIST[i]["role"] = MpGameRole.HIDER.value
            hiders += 1
          MP_INFO["num_hiders"] = hiders
          MP_INFO["num_hiders_left"] = hiders

          print("STARTING_SOON -> PLAY_HIDE")
          MP_INFO["state"] = MpGameState.PLAY_HIDE.value
          last_state_change_time = time.time()
      case MpGameState.PLAY_HIDE.value:
        # see if timer is up and we should begin seeking
        if time.time() - last_state_change_time >= MP_INFO["time_to_hide"]:
          print("PLAY_HIDE -> PLAY_SEEK")
          MP_INFO["state"] = MpGameState.PLAY_SEEK.value
          last_state_change_time = time.time()
      case MpGameState.PLAY_SEEK.value:
        # see if timer is up and we should end game
        if time.time() - last_state_change_time >= MP_INFO["hider_victory_timeout"]:
          print("PLAY_SEEK -> END (timeout - hiders win)")
          for i in range(len(PLAYER_LIST)):
            if (PLAYER_LIST[i] is None or PLAYER_LIST[i] == {}):
              continue
            if PLAYER_LIST[i]["role"] == MpGameRole.SEEKER.value:
              PLAYER_LIST[i]["rank"] = MP_INFO["num_hiders_left"] + 1
            elif PLAYER_LIST[i]["role"] == MpGameRole.HIDER.value:
              PLAYER_LIST[i]["rank"] = 1
            # else your rank should already be set

          MP_INFO["state"] = MpGameState.END.value
          last_state_change_time = time.time()

        active_hiders = player_counts[MpTargetState.HIDER_START] + player_counts[MpTargetState.HIDER_PLAY]
        active_seekers = player_counts[MpTargetState.SEEKER_WAIT] + player_counts[MpTargetState.SEEKER_START] + player_counts[MpTargetState.SEEKER_PLAY]
        # if no hiders left, then we should end game
        if active_seekers > 0 and active_hiders == 0:
          print("PLAY_SEEK -> END (no hiders - seekers win)")
          for i in range(len(PLAYER_LIST)):
            if (PLAYER_LIST[i] is None or PLAYER_LIST[i] == {}):
              continue
            if PLAYER_LIST[i]["role"] == MpGameRole.SEEKER.value:
              PLAYER_LIST[i]["rank"] = 1
            # else your rank should already be set
            
          MP_INFO["state"] = MpGameState.END.value
          last_state_change_time = time.time()
        # if no seekers, then we should end game
        if active_hiders > 0 and active_seekers == 0:
          print("PLAY_SEEK -> END (no seekers - hiders win)")
          for i in range(len(PLAYER_LIST)):
            if (PLAYER_LIST[i] is None or PLAYER_LIST[i] == {}):
              continue
            if PLAYER_LIST[i]["role"] == MpGameRole.HIDER.value:
              PLAYER_LIST[i]["rank"] = 1
            # else your rank should already be set

          MP_INFO["state"] = MpGameState.END.value
          last_state_change_time = time.time()
        # if no seekers or hiders... end game?
        if active_hiders == 0 and active_seekers == 0:
          print("PLAY_SEEK -> END (no seekers, no hiders???)")
          MP_INFO["state"] = MpGameState.END.value
          last_state_change_time = time.time()

      case MpGameState.END.value:
        # see if timer is up and we should go back to lobby
        if time.time() - last_state_change_time >= MP_INFO["post_game_timeout"]:
          print("END -> LOBBY")
          # TODO: reset state of everything
          MP_INFO["state"] = MpGameState.LOBBY.value
          last_state_change_time = time.time()

      # any clients should then update their own player states accordingly after seeing a game state change here

def run():
    print('Starting server...')

    game_thread = threading.Thread(target=game_loop)
    game_thread.start()

    # Server settings
    with HTTPServer(server_address, RequestHandler) as httpd:
      print('Server running at ' + server_address[0])
      server_thread = threading.Thread(target=httpd.serve_forever())
      server_thread.start()

if __name__ == '__main__':
    run()