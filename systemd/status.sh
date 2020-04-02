#!/bin/bash

systemctl status cloudflare-ddns.timer --no-pager
systemctl status cloudflare-ddns --no-pager
journalctl -u cloudflare-ddns -n 20
