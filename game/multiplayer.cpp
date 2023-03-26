#include "multiplayer.h"

#include <cstring>
#include <iomanip>
#include <map>
#include <sstream>
#include <string>
#include "game/kernel/common/Ptr.h"
#include "curl/curl.h"
#include "common/util/json_util.h"
#include "common/util/unicode_util.h"
#include <iostream>

#include "game/kernel/jak1/kscheme.h"
#include "game/runtime.h"
#include "third-party/json.hpp"
#include <filesystem>
#include <fstream>

using json = nlohmann::json;

std::string ipAddressOrHostname = "78.108.218.126:25560";

//This approach WILL break on release builds
void set_multiplayer_from_json() {
  // Get the current working directory
  std::filesystem::path currentDir = std::filesystem::current_path();

  // Walk back recursively until a directory called "jak-project" is found
  while (!currentDir.empty() && currentDir.filename() != "jak-project") {
    currentDir = currentDir.parent_path();
  }

  // Check if "jak-project" directory was found
  if (currentDir.empty()) {
    // Directory not found, set default values
    ipAddressOrHostname = "localhost:25560";
    return;
  }

  // Construct the path to the config.json file in the "jak-project/config" directory
  std::filesystem::path configPath = currentDir / "config" / "multiplayerconfig.json";

  // Check if the config.json file exists
  if (!std::filesystem::exists(configPath)) {
    // File not found, set default values
    ipAddressOrHostname = "localhost:25560";
    return;
  }

  // Read the JSON from the config file
  std::ifstream ifs(configPath);
  json config;
  ifs >> config;

  // Check if the "useExternalServer" key is set to true in the JSON file
  bool useExternalServer = config["useExternalServer"];

  // Set the ipAddressOrHostname variable based on the value of useExternalServer
  if (useExternalServer) {
    ipAddressOrHostname = config["externalServerAddress"];
  } else {
    ipAddressOrHostname = "localhost:25560";
  }
}

std::stringstream urlStream;

size_t curl_write_callbacka(char* ptr, size_t size, size_t nmemb, void* userdata) {
  size_t len = size * nmemb;
  std::string* response_data = reinterpret_cast<std::string*>(userdata);
  response_data->append(ptr, len);
  return len;
}

MultiplayerInfo* gMultiplayerInfo;
RemotePlayerInfo* gSelfPlayerInfo;
String* uname;

void http_register(u64 mpInfo, u64 selfPlayerInfo) {
  gMultiplayerInfo = Ptr<MultiplayerInfo>(mpInfo).c();
  gSelfPlayerInfo = Ptr<RemotePlayerInfo>(selfPlayerInfo).c();
  uname = Ptr<String>(gSelfPlayerInfo->username).c();

  // spawn new thread to handle parsing curl response
  std::thread([]() {
    // Initialize curl
    curl_global_cleanup();
    curl_global_init(CURL_GLOBAL_ALL);
    CURL* curl = curl_easy_init();

    // Set curl options
    std::string username = Ptr<String>(gSelfPlayerInfo->username).c()->data();
    std::string url = "http://" + ipAddressOrHostname + "/register?username=" + username;
    curl_easy_setopt(curl, CURLOPT_URL, url.c_str());
    curl_easy_setopt(curl, CURLOPT_POSTFIELDS, "foobar");
    curl_easy_setopt(curl, CURLOPT_WRITEFUNCTION, curl_write_callbacka);
    std::string response_data;
    curl_easy_setopt(curl, CURLOPT_WRITEDATA, &response_data);

    // Perform curl request
    CURLcode res = curl_easy_perform(curl);

    // Cleanup curl
    curl_easy_cleanup(curl);
    curl_global_cleanup();

    // Check if the request was successful
    if (res == CURLE_OK) {
      // Parse JSON response
      nlohmann::json response_json = nlohmann::json::parse(response_data);

      // Extract values from JSON response
      int player_num = response_json["player_num"];
      gMultiplayerInfo->player_num = player_num;
      RemotePlayerInfo* ownRpInfo = &(gMultiplayerInfo->players[gMultiplayerInfo->player_num]);
      strncpy(Ptr<String>(ownRpInfo->username).c()->data(), username.c_str(), MAX_USERNAME_LEN);
      int is_admin = response_json["is_admin"];
      ownRpInfo->is_admin = is_admin;
      if (is_admin == 1) {
        // if we just became admin, post our game settings
        http_update_settings();
      }
      int game_state = response_json["game_state"];
      gMultiplayerInfo->state = game_state;
    }
  }).detach();
}

void http_post_generic(const std::string& endpoint, const nlohmann::json& payload) {
  // spawn new thread to handle parsing curl response
  std::thread([endpoint, payload]() {
    // Initialize curl
    curl_global_cleanup();
    curl_global_init(CURL_GLOBAL_ALL);
    CURL* curl = curl_easy_init();

    std::string payload_str = payload.dump();

    // Set curl options
    curl_easy_setopt(curl, CURLOPT_URL, endpoint.c_str());
    curl_easy_setopt(curl, CURLOPT_POSTFIELDS, payload_str.c_str());
    curl_easy_setopt(curl, CURLOPT_WRITEFUNCTION, curl_write_callbacka);
    std::string response_data;
    curl_easy_setopt(curl, CURLOPT_WRITEDATA, &response_data);

    // Perform curl request
    CURLcode res = curl_easy_perform(curl);

    // Cleanup curl
    curl_easy_cleanup(curl);
    curl_global_cleanup();

    // Check if the request was successful
    if (res == CURLE_OK) {
      // assume no action needed after update
    }
  }).detach();
}

void http_mark_found(int idx) {
  RemotePlayerInfo* ownRpInfo = &(gMultiplayerInfo->players[gMultiplayerInfo->player_num]);
  RemotePlayerInfo* foundRpInfo = &(gMultiplayerInfo->players[idx]);

  std::string url = "http://" + ipAddressOrHostname + "/mark_found";

  // Construct JSON payload
  nlohmann::json payload = {{"seeker_username", Ptr<String>(ownRpInfo->username).c()->data()},
                            {"found_username", Ptr<String>(foundRpInfo->username).c()->data()}};

  http_post_generic(url, payload);
}

void http_update_settings() {
  RemotePlayerInfo* rpInfo = &(gMultiplayerInfo->players[gMultiplayerInfo->player_num]);
  std::string username = Ptr<String>(rpInfo->username).c()->data();
  std::string url = "http://" + ipAddressOrHostname + "/update_settings?username=" + username;

  // Construct JSON payload
  nlohmann::json payload = {
    {"target_hider_type", gMultiplayerInfo->hide_and_seek_game_info.target_hider_type},
    {"level_mode", gMultiplayerInfo->hide_and_seek_game_info.level_mode},
    {"continue_point_mode", gMultiplayerInfo->hide_and_seek_game_info.continue_point_mode},
    {"hiders_move", gMultiplayerInfo->hide_and_seek_game_info.hiders_move},
    {"hiders_pause_zoom", gMultiplayerInfo->hide_and_seek_game_info.hiders_pause_zoom},
    {"seekers_infect", gMultiplayerInfo->hide_and_seek_game_info.seekers_infect},
    {"num_seekers", gMultiplayerInfo->hide_and_seek_game_info.num_seekers},
    {"last_winner_as_seeker", gMultiplayerInfo->hide_and_seek_game_info.last_winner_as_seeker},
    {"fog_distance", gMultiplayerInfo->hide_and_seek_game_info.fog_distance},
    {"hider_speed", gMultiplayerInfo->hide_and_seek_game_info.hider_speed},
    {"seeker_speed", gMultiplayerInfo->hide_and_seek_game_info.seeker_speed},
    {"time_to_start", gMultiplayerInfo->hide_and_seek_game_info.time_to_start},
    {"time_to_hide", gMultiplayerInfo->hide_and_seek_game_info.time_to_hide},
    {"hider_victory_timeout", gMultiplayerInfo->hide_and_seek_game_info.hider_victory_timeout},
    {"post_game_timeout", gMultiplayerInfo->hide_and_seek_game_info.post_game_timeout},
  };

  http_post_generic(url, payload);
}

void http_update() {
  RemotePlayerInfo* rpInfo = &(gMultiplayerInfo->players[gMultiplayerInfo->player_num]);

  std::string username = Ptr<String>(rpInfo->username).c()->data();
  std::string url = "http://" + ipAddressOrHostname + "/update?username=" + username;

  // Construct JSON payload
  nlohmann::json payload = {
      {"username", username},
      {"color", rpInfo->color},
      // is_admin intentionally left out, only updated from server side
      {"trans_x", rpInfo->trans_x},
      {"trans_y", rpInfo->trans_y},
      {"trans_z", rpInfo->trans_z},
      {"quat_x", rpInfo->quat_x},
      {"quat_y", rpInfo->quat_y},
      {"quat_z", rpInfo->quat_z},
      {"quat_w", rpInfo->quat_w},
      {"tgt_state", rpInfo->tgt_state},
      // role intentionally left out, only updated from server side
      // collected_by_pnum intentionally left out, only updated from server side
      // rank intentionally left out, only updated from server side
      {"mp_state", rpInfo->hns_info.mp_state}
  };

  http_post_generic(url, payload);
}

void http_get() {
  // spawn new thread to handle parsing curl response
  std::thread([]() {
    // Initialize curl
    curl_global_cleanup();
    curl_global_init(CURL_GLOBAL_ALL);
    CURL* curl = curl_easy_init();

    std::string url = "http://" + ipAddressOrHostname + "/get";

    // Set curl options
    curl_easy_setopt(curl, CURLOPT_URL, url.c_str());
    curl_easy_setopt(curl, CURLOPT_WRITEFUNCTION, curl_write_callbacka);
    std::string response_data;
    curl_easy_setopt(curl, CURLOPT_WRITEDATA, &response_data);

    // Perform curl request
    CURLcode res = curl_easy_perform(curl);

    // Cleanup curl
    curl_easy_cleanup(curl);
    curl_global_cleanup();

    // Check if the request was successful
    if (res == CURLE_OK) {
      // Parse JSON response
      nlohmann::json response_json = nlohmann::json::parse(response_data);

      // game state
      int game_state = response_json["game_state"];
      gMultiplayerInfo->state = game_state;
      int alert_found_pnum = response_json["alert_found_pnum"];
      gMultiplayerInfo->hide_and_seek_game_info.alert_found_pnum = alert_found_pnum;
      int alert_seeker_pnum = response_json["alert_seeker_pnum"];
      gMultiplayerInfo->hide_and_seek_game_info.alert_seeker_pnum = alert_seeker_pnum;
      int num_hiders = response_json["num_hiders"];
      gMultiplayerInfo->hide_and_seek_game_info.num_hiders = num_hiders;
      int num_hiders_left = response_json["num_hiders_left"];
      gMultiplayerInfo->hide_and_seek_game_info.num_hiders_left = num_hiders_left;

      // players
      for (const auto& item : response_json["players"].items()) {
        int pNum = stoi(item.key());
        if (pNum < MAX_MULTIPLAYER_COUNT) {
          RemotePlayerInfo* rpInfo = &(gMultiplayerInfo->players[pNum]);

          for (const auto& field : item.value().items()) {
            if (field.key().compare("username") == 0) {
              // str copy username into struct
              std::string uname = field.value();
              strncpy(Ptr<String>(rpInfo->username).c()->data(), uname.c_str(), MAX_USERNAME_LEN);
            } else if (field.key().compare("color") == 0) {
              rpInfo->color = field.value();
            } else if (field.key().compare("is_admin") == 0) {
              rpInfo->is_admin = field.value();
            } else if (field.key().compare("trans_x") == 0) {
              rpInfo->trans_x = field.value();
            } else if (field.key().compare("trans_y") == 0) {
              rpInfo->trans_y = field.value();
            } else if (field.key().compare("trans_z") == 0) {
              rpInfo->trans_z = field.value();
            } else if (field.key().compare("quat_x") == 0) {
              rpInfo->quat_x = field.value();
            } else if (field.key().compare("quat_y") == 0) {
              rpInfo->quat_y = field.value();
            } else if (field.key().compare("quat_z") == 0) {
              rpInfo->quat_z = field.value();
            } else if (field.key().compare("quat_w") == 0) {
              rpInfo->quat_w = field.value();
            } else if (field.key().compare("tgt_state") == 0) {
              rpInfo->tgt_state = field.value();
            } else if (field.key().compare("role") == 0) {
              rpInfo->hns_info.role = field.value();
            } else if (field.key().compare("mp_state") == 0
              && pNum != gMultiplayerInfo->player_num) { // only sync mp_state for remotes. for our own target, only goal code should be updating this
              rpInfo->hns_info.mp_state = field.value();
            } else if (field.key().compare("collected_by_pnum") == 0) {
              rpInfo->hns_info.collected_by_pnum = field.value();
            } else if (field.key().compare("rank") == 0) {
              rpInfo->hns_info.rank = field.value();
            }
          }
        }
      }

      RemotePlayerInfo* ownRpInfo = &(gMultiplayerInfo->players[gMultiplayerInfo->player_num]);
      if (ownRpInfo->is_admin == 0) {  // not admin, we get settings from server
        u32 target_hider_type = response_json["target_hider_type"];
        gMultiplayerInfo->hide_and_seek_game_info.target_hider_type = target_hider_type;
        u32 level_mode = response_json["level_mode"];
        gMultiplayerInfo->hide_and_seek_game_info.level_mode = level_mode;
        u32 continue_point_mode = response_json["continue_point_mode"];
        gMultiplayerInfo->hide_and_seek_game_info.continue_point_mode = continue_point_mode;
        int hiders_move = response_json["hiders_move"];
        gMultiplayerInfo->hide_and_seek_game_info.hiders_move = hiders_move;
        int hiders_pause_zoom = response_json["hiders_pause_zoom"];
        gMultiplayerInfo->hide_and_seek_game_info.hiders_pause_zoom = hiders_pause_zoom;
        int seekers_infect = response_json["seekers_infect"];
        gMultiplayerInfo->hide_and_seek_game_info.seekers_infect = seekers_infect;
        int num_seekers = response_json["num_seekers"];
        gMultiplayerInfo->hide_and_seek_game_info.num_seekers = num_seekers;
        int last_winner_as_seeker = response_json["last_winner_as_seeker"];
        gMultiplayerInfo->hide_and_seek_game_info.last_winner_as_seeker = last_winner_as_seeker;
        float fog_distance = response_json["fog_distance"];
        gMultiplayerInfo->hide_and_seek_game_info.fog_distance = fog_distance;
        float hider_speed = response_json["hider_speed"];
        gMultiplayerInfo->hide_and_seek_game_info.hider_speed = hider_speed;
        float seeker_speed = response_json["seeker_speed"];
        gMultiplayerInfo->hide_and_seek_game_info.seeker_speed = seeker_speed;
        int time_to_start = response_json["time_to_start"];
        gMultiplayerInfo->hide_and_seek_game_info.time_to_start = time_to_start;
        int time_to_hide = response_json["time_to_hide"];
        gMultiplayerInfo->hide_and_seek_game_info.time_to_hide = time_to_hide;
        int hider_victory_timeout = response_json["hider_victory_timeout"];
        gMultiplayerInfo->hide_and_seek_game_info.hider_victory_timeout = hider_victory_timeout;
        int post_game_timeout = response_json["post_game_timeout"];
        gMultiplayerInfo->hide_and_seek_game_info.post_game_timeout = post_game_timeout;
      }
    }
  }).detach();
}
