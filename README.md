# cfddns

Yet another DDNS client for Cloudflare written in Rust.

[![Packaging status](https://repology.org/badge/vertical-allrepos/cfddns.svg)](https://repology.org/project/cfddns/versions)

## Usage

```
cfddns -c <config.yml> <domain-list.txt>
```

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

Install `cfddns` from [AUR](https://aur.archlinux.org/packages/cfddns/).

```bash
yay -S cfddns
```

```bash
vim /etc/cfddns/cfddns.yml # replace `token` value with yours
vim /etc/cfddns/domains

systemctl enable --now cfddns
```

### Cargo

```
cargo install cfddns
```

### Build from source

```bash
git clone https://github.com/uetchy/cfddns.git && cd cfddns
cargo build --release
cp target/release/cfddns /usr/local/bin
```

## Contribute

### Tasks

- Report a bug
- Create and maintain `cfddns` package for your favorite Linux distribution
