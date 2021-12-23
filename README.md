# cfddns

Ergonomic dynamic DNS (DDNS) client for Cloudflare.

[![Packaging status](https://repology.org/badge/vertical-allrepos/cfddns.svg)](https://repology.org/project/cfddns/versions)

## Usage

```bash
cat << EOD > domains
example.com
mail.example.com
example.org
EOD

cat <<EOD > cfddns.yml
token: "<CloudFlare API token>"
interval: 900 # in seconds (optional)
endpoint: "https://api.ipify.org" # external ip provider (optional)
EOD

cfddns -c cfddns.yml domains
```

## Install

### Arch Linux

Install `cfddns` via [AUR](https://aur.archlinux.org/packages/cfddns/).

```bash
git clone https://aur.archlinux.org/cfddns.git && cd cfddns
makepkg -si
# or just `yay -S cfddns`

cat << EOD > /etc/cfddns/domains
example.com
mail.example.com
example.org
EOD

vim /etc/cfddns/cfddns.yml # assign `token`

systemctl enable --now cfddns
```

### pip

```
pip install cfddns
```

### Build from source

```bash
git clone https://github.com/uetchy/cfddns.git && cd cfddns
poetry install --build
```

## Contribute

### Tasks

- Create and maintain a package of cfddns for your favorite Linux distribution
- Report a bug
