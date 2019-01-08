# CloudFlare DDNS

Multiple FQDN Dynamic DNS Updater for CloudFlare DNS.

based on [example_update_dynamic_dns.py](https://github.com/cloudflare/python-cloudflare/blob/master/examples/example_update_dynamic_dns.py).

## Usage

```
cat << EOD > list.txt
example.com
a.example.com
b.example.org
EOD
python3 update.py list.txt
```
