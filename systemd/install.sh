#!/bin/bash

SYSTEM_PATH=/etc/systemd/system

cp cloudflare-ddns.service cloudflare-ddns.timer $SYSTEM_PATH
