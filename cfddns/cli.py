#!/usr/bin/env python3
# based on examples/example_update_dynamic_dns.py
# at https://github.com/cloudflare/python-cloudflare

import asyncio
import re
import time
from datetime import datetime

import click
import CloudFlare
import requests
import yaml
import time

from .notification import send_notification


def get_ip_address(endpoint, logger):
    try:
        retry_count = 3
        while retry_count > 0:
            res = requests.get(endpoint)
            if res.status_code == 200:
                ip_address = res.text.strip()
                break
            retry_count -= 1
            time.sleep(5)

        if retry_count == 0:
            logger('looks like %s is unavailable' % endpoint)
            return

    except Exception:
        logger('%s failed' % endpoint)
        return

    if ip_address == '':
        logger('%s failed' % endpoint)
        return

    if ':' in ip_address:
        ip_address_type = 'AAAA'
    else:
        ip_address_type = 'A'

    return ip_address, ip_address_type


def update_record(cf, zone_id, dns_name, ip_address, ip_address_type, logger):
    params = {'name': dns_name, 'match': 'all', 'type': ip_address_type}

    try:
        dns_records = cf.zones.dns_records.get(zone_id, params=params)
    except CloudFlare.exceptions.CloudFlareAPIError as e:
        exit('/zones/dns_records %s - %s - api call failed' % (dns_name, e))
    updated = False
    should_inform = False

    for dns_record in dns_records:
        old_ip_address = dns_record['content']
        old_ip_address_type = dns_record['type']

        if ip_address_type not in ['A', 'AAAA']:
            continue

        if ip_address_type != old_ip_address_type:
            logger('ignored: %s %s; wrong address family' %
                   (dns_name, old_ip_address))
            should_inform = True
            continue

        if ip_address == old_ip_address:
            logger('unchanged: %s %s' % (dns_name, ip_address))
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
            logger('/zones.dns_records.put %s %s - api call failed' %
                   (dns_name, e))
            return True
        logger('update: %s %s -> %s' % (dns_name, old_ip_address, ip_address))
        updated = True
        should_inform = True

    if updated:
        return should_inform

    should_inform = True

    # no exsiting dns record to update - so create dns record
    dns_record = {
        'name': dns_name,
        'type': ip_address_type,
        'content': ip_address
    }
    try:
        dns_record = cf.zones.dns_records.post(zone_id, data=dns_record)
    except CloudFlare.exceptions.CloudFlareAPIError as e:
        logger('/zones.dns_records.post %s %s - api call failed' %
               (dns_name, e))
        return True
    logger('created: %s %s' % (dns_name, ip_address))
    return should_inform


def update_domain(dns_name, ip_address, ip_address_type, token, logger):
    zone_name = re.compile("\.(?=.+\.)").split(dns_name)[-1]
    # print('pending: %s' % dns_name)

    cf = CloudFlare.CloudFlare(token=token)

    try:
        params = {'name': zone_name}
        zones = cf.zones.get(params=params)
    except CloudFlare.exceptions.CloudFlareAPIError as e:
        logger('/zones %s - api call failed. check if token is set' % e)
        return True
    except Exception as e:
        logger('/zones.get - %s - api call failed' % e)
        return True

    if len(zones) == 0:
        logger('/zones.get - %s - zone not found' % zone_name)
        return True

    if len(zones) != 1:
        logger('/zones.get - %s - api call returned {len(zones)} items' %
               zone_name)
        return True

    zone = zones[0]

    zone_name = zone['name']
    zone_id = zone['id']

    return update_record(cf,
                         zone_id,
                         dns_name,
                         ip_address,
                         ip_address_type,
                         logger=logger)


def update(dns_list, token, endpoint, logger):
    logger('\nstart: %s' % datetime.now())

    ip = get_ip_address(endpoint, logger=logger)
    if ip is None:
        return True

    ip_address, ip_address_type = ip
    logger('ip: %s' % ip_address)

    should_inform = False
    for dns_name in dns_list:
        changed = update_domain(dns_name,
                                ip_address,
                                ip_address_type,
                                token=token,
                                logger=logger)
        should_inform = should_inform | changed

    logger('done: %s' % datetime.now())
    return should_inform


@click.command()
@click.argument('domains', type=click.File('r'))
@click.option('--config',
              '-c',
              type=click.File('r'),
              help='path to config file',
              required=True)
def main(domains, config):
    time.tzset()
    dns_list = domains.read().splitlines()
    conf = yaml.full_load(config)
    interval = conf.get('interval', 600)
    endpoint = conf.get('endpoint', "https://api.ipify.org")
    token = conf['token']

    notification_enabled = False
    notification_conf = conf.get('notification', None)
    if notification_conf:
        mail_from = notification_conf.get('from')
        mail_to = notification_conf.get('to')
        notification_enabled = notification_conf.get('enabled', False)

    print('interval: %s' % interval)
    print('endpoint: %s' % endpoint)

    log_buffer = []

    def logger(text):
        log_buffer.append(text)
        print(text, flush=True)

    async def wrapper():
        while True:
            should_inform = update(dns_list, token, endpoint, logger=logger)
            if should_inform and notification_enabled:
                log = "\n".join(log_buffer)
                send_notification(mail_from, mail_to, "cfddns", log)
            log_buffer.clear()
            await asyncio.sleep(interval)

    asyncio.run(wrapper())
