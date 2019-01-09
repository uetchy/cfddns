#!/bin/bash

SYSTEM_PATH=/etc/systemd/system

rm $SYSTEM_PATH/cloudflare-ddns.service $SYSTEM_PATH/cloudflare-ddns.timer
