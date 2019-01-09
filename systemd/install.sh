#!/bin/bash

ROOT_DIR=$(realpath $(dirname $0)/../)
CONF_DIR=$ROOT_DIR/systemd
SYSTEM_PATH=/etc/systemd/system

cat $CONF_DIR/cloudflare-ddns.service | sed "s|{{ROOT_DIR}}|$ROOT_DIR|g" >$SYSTEM_PATH/cloudflare-ddns.service
cp $SCRIPT_DIR/cloudflare-ddns.timer $SYSTEM_PATH/cloudflare-ddns.timer
