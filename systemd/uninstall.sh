#!/bin/bash

SYSTEM_PATH=/etc/systemd/system

rm $SYSTEM_PATH/cloudflare-ddns.service
rm $SYSTEM_PATH/cloudflare-ddns.timer
