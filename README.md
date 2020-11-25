# CloudFlare DDNS

DDNS Updater for CloudFlare.

based on [example_update_dynamic_dns.py](https://github.com/cloudflare/python-cloudflare/blob/master/examples/example_update_dynamic_dns.py).

## Usage

```bash
cat << EOD > domains.txt
example.com
a.example.com
b.example.org
EOD
python3 src/update.py domains.txt
```

### Docker Compose

```bash
docker-compose up -d
```
