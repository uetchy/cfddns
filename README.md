# cfddns

DDNS Updater for CloudFlare.

## Usage

```bash
cat << EOD > domains
example.com
mail.example.com
example.org
EOD

cfddns -c cfddns.yml domains
```
