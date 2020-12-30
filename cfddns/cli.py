#!/usr/bin/env python3
# based on examples/example_update_dynamic_dns.py
# at https://github.com/cloudflare/python-cloudflare

import sys
import re
from datetime import datetime
import time
import threading
import CloudFlare
import requests
import click
import yaml


def get_ip_address(endpoint):
    try:
        ip_address = requests.get(endpoint).text
    except Exception:
        exit('%s failed' % endpoint)

    if ip_address == '':
        exit('%s failed' % endpoint)

    if ':' in ip_address:
        ip_address_type = 'AAAA'
    else:
        ip_address_type = 'A'

    return ip_address, ip_address_type


def update_zone(cf, zone_name, zone_id, dns_name, ip_address, ip_address_type):
    params = {'name': dns_name, 'match': 'all', 'type': ip_address_type}

    try:
        dns_records = cf.zones.dns_records.get(zone_id, params=params)
    except CloudFlare.exceptions.CloudFlareAPIError as e:
        exit('/zones/dns_records %s - %s - api call failed' % (dns_name, e))
    updated = False

    for dns_record in dns_records:
        old_ip_address = dns_record['content']
        old_ip_address_type = dns_record['type']

        if ip_address_type not in ['A', 'AAAA']:
            continue

        if ip_address_type != old_ip_address_type:
            print('ignored: %s %s; wrong address family' %
                  (dns_name, old_ip_address))
            continue

        if ip_address == old_ip_address:
            print('unchanged: %s %s' % (dns_name, ip_address))
            updated = True
            continue

        # Yes, we need to update this record - we know it's the same address type

        dns_record_id = dns_record['id']
        dns_record = {
            'name': dns_name,
            'type': ip_address_type,
            'content': ip_address
        }
        try:
            dns_record = cf.zones.dns_records.put(zone_id,
                                                  dns_record_id,
                                                  data=dns_record)
        except CloudFlare.exceptions.CloudFlareAPIError as e:
            exit('/zones.dns_records.put %s %s - api call failed' %
                 (dns_name, e))
        print('update: %s %s -> %s' % (dns_name, old_ip_address, ip_address))
        updated = True

    if updated:
        return

    # no exsiting dns record to update - so create dns record
    dns_record = {
        'name': dns_name,
        'type': ip_address_type,
        'content': ip_address
    }
    try:
        dns_record = cf.zones.dns_records.post(zone_id, data=dns_record)
    except CloudFlare.exceptions.CloudFlareAPIError as e:
        exit('/zones.dns_records.post %s %s - api call failed' % (dns_name, e))
    print('created: %s %s' % (dns_name, ip_address))


def update_fqdn(dns_name, ip_address, ip_address_type, token):
    zone_name = re.compile("\.(?=.+\.)").split(dns_name)[-1]
    # print('pending: %s' % dns_name)

    cf = CloudFlare.CloudFlare(token=token)

    try:
        params = {'name': zone_name}
        zones = cf.zones.get(params=params)
    except CloudFlare.exceptions.CloudFlareAPIError as e:
        exit('/zones %s - api call failed. check if token is set' % e)
    except Exception as e:
        exit('/zones.get - %s - api call failed' % e)

    if len(zones) == 0:
        exit('/zones.get - %s - zone not found' % zone_name)

    if len(zones) != 1:
        exit('/zones.get - %s - api call returned {len(zones)} items' %
             zone_name)

    zone = zones[0]

    zone_name = zone['name']
    zone_id = zone['id']

    update_zone(cf, zone_name, zone_id, dns_name, ip_address, ip_address_type)


@click.command()
@click.argument('domains', type=click.File('r'))
@click.option('--config',
              '-c',
              type=click.File('r'),
              help='path to config file',
              required=True)
def main(domains, config):
    time.tzset()
    print('start: %s' % datetime.now())

    dns_list = domains.read().splitlines()
    conf = yaml.full_load(config)
    token = conf['token']
    endpoint = conf.get('endpoint', "https://api.ipify.org")
    interval = conf.get('interval', 300)

    ip_address, ip_address_type = get_ip_address(endpoint)
    print('ip: %s' % ip_address)

    for dns_name in dns_list:
        update_fqdn(
            dns_name,
            ip_address,
            ip_address_type,
            token=token,
        )

    print('done: %s' % datetime.now())
    print('wait: %s' % interval)
    threading.Timer(interval, main).start()