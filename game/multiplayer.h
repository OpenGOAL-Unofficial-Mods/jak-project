#pragma once

#include "kernel/common/kernel_types.h"

void http_register(u64 mpInfo, u64 selfPlayerInfo);
void http_update();
void http_update_settings();
void http_mark_found(int idx);
void http_get();
void set_multiplayer_from_json();
void read_username_from_file(char* username);
extern char username[101];
