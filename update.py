#!/usr/bin/env python3
# based on examples/example_update_dynamic_dns.py
# at https://github.com/cloudflare/python-cloudflare

import sys
import CloudFlare
import requests


def get_ip_address():
    endpoint = 'https://api.ipify.org'
    try:
        ip_address = requests.get(endpoint).text
    except Exception:
        exit(f'{endpoint}: failed')

    if ip_address == '':
        exit(f'{endpoint}: failed')

    if ':' in ip_address:
        ip_address_type = 'AAAA'
    else:
        ip_address_type = 'A'

    return ip_address, ip_address_type


def update_dns(cf, zone_name, zone_id, dns_name, ip_address, ip_address_type):
    params = {'name': dns_name, 'match': 'all', 'type': ip_address_type}

    try:
        dns_records = cf.zones.dns_records.get(zone_id, params=params)
    except CloudFlare.exceptions.CloudFlareAPIError as e:
        exit(f'/zones/dns_records {dns_name} - {e} - api call failed')
    updated = False

    for dns_record in dns_records:
        old_ip_address = dns_record['content']
        old_ip_address_type = dns_record['type']

        if ip_address_type not in ['A', 'AAAA']:
            continue

        if ip_address_type != old_ip_address_type:
            print(f'ignored: {dns_name} {old_ip_address}; wrong address family')
            continue

        if ip_address == old_ip_address:
            print(f'unchanged: {dns_name} {ip_address}')
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
            dns_record = cf.zones.dns_records.put(
                zone_id, dns_record_id, data=dns_record)
        except CloudFlare.exceptions.CloudFlareAPIError as e:
            exit(f'/zones.dns_records.put {dns_name} - {e} - api call failed')
        print(f'update: {dns_name} {old_ip_address} -> {ip_address}')
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
        exit(f'/zones.dns_records.post {dns_name} - {e} - api call failed')
    print(f'CREATED: {dns_name} {ip_address}')


def update_fqdn(dns_name, ip_address, ip_address_type):
    host_name, zone_name = dns_name.split('.', 1)
    print(f'pending: {dns_name}')

    cf = CloudFlare.CloudFlare()

    try:
        params = {'name': zone_name}
        zones = cf.zones.get(params=params)
    except CloudFlare.exceptions.CloudFlareAPIError as e:
        exit(f'/zones {e} - api call failed')
    except Exception as e:
        exit(f'/zones.get - {e} - api call failed')

    if len(zones) == 0:
        exit(f'/zones.get - {zone_name} - zone not found')

    if len(zones) != 1:
        exit(f'/zones.get - {zone_name} - api call returned {len(zones)} items')

    zone = zones[0]

    zone_name = zone['name']
    zone_id = zone['id']

    update_dns(cf, zone_name, zone_id, dns_name, ip_address, ip_address_type)


if __name__ == '__main__':
    try:
        dns_list_path = sys.argv[1]
    except IndexError:
        exit('usage: update.py fqdn-hostname')

    with open(dns_list_path) as f:
        dns_list = f.read().splitlines()

    ip_address, ip_address_type = get_ip_address()
    print(f'ip: {ip_address}')

    for dns_name in dns_list:
        update_fqdn(dns_name, ip_address, ip_address_type)
