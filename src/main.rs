use std::collections::{HashMap, HashSet};
use std::net::Ipv4Addr;
use std::path::PathBuf;
use std::str::FromStr;
use std::time::Duration;

use anyhow::{anyhow, bail, Result};
use clap::Parser;
use cloudflare::endpoints::dns::{DnsContent, DnsRecord};
use cloudflare::endpoints::{dns, zone};
use cloudflare::framework::{
    async_api::{ApiClient, Client},
    auth::Credentials,
    Environment, HttpApiClientConfig, OrderDirection,
};
use lettre::transport::smtp;
use lettre::{Message, SmtpTransport, Transport};
use serde::{Deserialize, Serialize};
use serde_yaml;
use tokio::{task, time};

// stolen from https://docs.rs/once_cell/latest/once_cell/index.html
// MIT @ Aleksey Kladov <aleksey.kladov@gmail.com>
macro_rules! regex {
    ($re:literal $(,)?) => {{
        static RE: once_cell::sync::OnceCell<regex::Regex> = once_cell::sync::OnceCell::new();
        RE.get_or_init(|| regex::Regex::new($re).unwrap())
    }};
}

#[derive(Debug, Serialize, Deserialize)]
struct NotificationConfig {
    /// Enable email notification
    enabled: bool,

    /// Sender address
    from: String,

    /// Recipient address
    to: String,
}

#[derive(Debug, Serialize, Deserialize)]
struct Config {
    /// Cloudflare token (required)
    token: String,

    /// Update interval in seconds (default: 600)
    interval: Option<u64>,

    /// External IP address provider (default: "https://api.ipify.org")
    endpoint: Option<String>,

    /// Email notification config (default: undefined)
    notification: Option<NotificationConfig>,
}

#[derive(Parser, Debug)]
#[clap(
    author,
    version,
    about,
    long_about = "Yet another DDNS client for Cloudflare
[MANUAL] https://github.com/uetchy/cfddns#readme"
)]
struct Args {
    /// Path to domain list file
    domains: PathBuf,

    /// Path to config file
    #[clap(short, long)]
    config: PathBuf,
}

#[derive(Debug)]
pub struct MuxWriter {
    pub buf: Vec<String>,
    pub should_notify: bool,
}

impl MuxWriter {
    pub fn new() -> Self {
        Self {
            buf: vec![],
            should_notify: false,
        }
    }

    pub fn mark(&mut self) {
        self.should_notify = true;
    }

    pub fn write(&mut self, data: String) {
        println!("{}", data);
        self.buf.push(data);
    }

    pub fn drain(&mut self) -> (String, bool) {
        let result = self.buf.join("\n").clone();
        let should_notify = self.should_notify;
        self.buf.clear();
        self.should_notify = false;
        (result, should_notify)
    }
}

#[tokio::main]
async fn main() -> Result<()> {
    // parse args
    let args = Args::parse();
    let config_path = args.config;
    let domain_list_path = args.domains;

    // load config
    let config = load_config(&config_path)?;
    let token = config.token.clone();
    let interval = config.interval.unwrap_or(600);
    let endpoint = config
        .endpoint
        .clone()
        .unwrap_or_else(|| "https://api.ipify.org".to_string());

    // instantiate cloudflare client
    let credentials: Credentials = Credentials::UserAuthToken { token };
    let api_client = Client::new(
        credentials,
        HttpApiClientConfig::default(),
        Environment::Production,
    )?;

    // preload zone list
    let mut zone_name_id_map: HashMap<String, String> = HashMap::new();
    let zones = list_zones(&api_client).await?;
    for zone in zones {
        zone_name_id_map.insert(zone.name, zone.id);
    }

    // load domain list
    let domain_list = load_domain_list(&domain_list_path)?
        .iter()
        .map(|x| {
            let (fqdn, zone_name) = split_hostname(x).unwrap();
            (fqdn, zone_name_id_map.get(&zone_name).unwrap().to_owned())
        })
        .collect::<Vec<(String, String)>>();

    let mut writer = MuxWriter::new();

    let forever = task::spawn(async move {
        let mut interval = time::interval(Duration::from_secs(interval));

        loop {
            interval.tick().await;

            println!("Started checking DNS records...");

            let (response, should_notify): (String, bool) =
                match populate_ips(&domain_list, &api_client, &endpoint, &mut writer).await {
                    Ok(()) => writer.drain(),
                    Err(err) => (format!("{}", err), true),
                };

            // notify the result
            if let Some(nc) = &config.notification {
                if nc.enabled && should_notify {
                    println!("Sending an email with config: {:?}", nc);
                    match send_mail(&nc.from, &nc.to, "cfddns", &response) {
                        Ok(_) => {}
                        Err(err) => println!("{}", err),
                    }
                }
            }
        }
    });

    forever.await.unwrap();

    Ok(())
}

async fn populate_ips<ApiClientType: ApiClient>(
    domain_list: &Vec<(String, String)>,
    api_client: &ApiClientType,
    endpoint: &str,
    writer: &mut MuxWriter,
) -> Result<()> {
    let global_ipv4_addr = get_global_ipv4_addr(&endpoint).await?;
    writer.write(format!("Current IP address: {}", global_ipv4_addr));

    // Build zone id cache
    let unique_zone_ids: HashSet<String> = domain_list.iter().map(|x| x.1.clone()).collect();
    let mut fqdn_record_cache: HashMap<String, DnsRecord> = HashMap::new();
    for zone_id in unique_zone_ids {
        let records = list_dns_records(&zone_id, api_client).await?;
        for record in records.into_iter().filter(|x| match x.content {
            DnsContent::A { content: _ } => true,
            _ => false,
        }) {
            fqdn_record_cache.insert(record.name.clone(), record);
        }
    }

    for (fqdn, zone_id) in domain_list {
        let record = fqdn_record_cache
            .iter()
            .find(|x| x.0.eq(fqdn))
            .and_then(|x| Some(x.1));

        if let Some(record) = record {
            let record_ip = match record.content {
                DnsContent::A { content: ip } => ip,
                _ => bail!("Invalid content type"),
            };

            if record_ip.ne(&global_ipv4_addr) {
                writer.mark();
                writer.write(format!(
                    "Updating A record for {}: {} -> {}",
                    fqdn, record_ip, global_ipv4_addr
                ));
                update_dns_record(
                    zone_id,
                    &record.id,
                    dns::UpdateDnsRecordParams {
                        ttl: Some(1),
                        proxied: Some(false),
                        name: fqdn,
                        content: dns::DnsContent::A {
                            content: global_ipv4_addr,
                        },
                    },
                    api_client,
                )
                .await?;
            } else {
                writer.write(format!("Unchanged {} ({})", fqdn, record_ip));
            }
        } else {
            writer.mark();
            writer.write(format!(
                "Creating A record for {} ({})",
                fqdn, global_ipv4_addr
            ));
            create_dns_record(
                zone_id,
                dns::CreateDnsRecordParams {
                    ttl: Some(1),
                    priority: None,
                    proxied: Some(false),
                    name: fqdn,
                    content: dns::DnsContent::A {
                        content: global_ipv4_addr,
                    },
                },
                api_client,
            )
            .await?;
        }
    }

    Ok(())
}

fn load_config(config_path: &PathBuf) -> Result<Config> {
    let f = std::fs::File::open(config_path)?;
    let config: Config = serde_yaml::from_reader(f)?;
    Ok(config)
}

/// returns `(fqdn, zone)`
fn split_hostname(name: &str) -> Option<(String, String)> {
    let re = regex!(r"^(?:[^.]+\.)*?((?:[^.]+\.?){2})$");
    let cap = re.captures(name).and_then(|cap| {
        let fqdn = cap.get(0)?.as_str().to_owned();
        let zone = cap.get(1)?.as_str().to_owned();
        Some((fqdn, zone))
    });
    cap
}

async fn get_global_ipv4_addr(endpoint: &str) -> Result<Ipv4Addr> {
    let body = reqwest::get(endpoint).await?.text().await?;
    match Ipv4Addr::from_str(&body) {
        Ok(res) => Ok(res),
        Err(err) => bail!(err),
    }
}

fn load_domain_list(path: &PathBuf) -> Result<Vec<String>> {
    let data = std::fs::read_to_string(path)?;
    let list = data
        .split("\n")
        .filter(|s| !s.is_empty())
        .map(String::from)
        .collect::<Vec<String>>();
    Ok(list)
}

async fn list_zones<ApiClientType: ApiClient>(
    api_client: &ApiClientType,
) -> Result<Vec<zone::Zone>> {
    let response = api_client
        .request(&zone::ListZones {
            params: zone::ListZonesParams {
                ..Default::default()
            },
        })
        .await;
    match response {
        Ok(res) => Ok(res.result),
        Err(err) => bail!(err),
    }
}

async fn list_dns_records<ApiClientType: ApiClient>(
    zone_identifier: &str,
    api_client: &ApiClientType,
) -> Result<Vec<dns::DnsRecord>> {
    let response = api_client
        .request(&dns::ListDnsRecords {
            zone_identifier,
            params: dns::ListDnsRecordsParams {
                direction: Some(OrderDirection::Ascending),
                ..Default::default()
            },
        })
        .await;
    match response {
        Ok(res) => Ok(res.result),
        Err(err) => bail!(err),
    }
}

async fn create_dns_record<'a, ApiClientType: ApiClient>(
    zone_identifier: &str,
    params: dns::CreateDnsRecordParams<'a>,
    api_client: &ApiClientType,
) -> Result<DnsRecord> {
    let response = api_client
        .request(&dns::CreateDnsRecord {
            zone_identifier,
            params,
        })
        .await;
    match response {
        Ok(res) => Ok(res.result),
        Err(err) => bail!(err),
    }
}

async fn update_dns_record<'a, ApiClientType: ApiClient>(
    zone_identifier: &str,
    identifier: &str,
    params: dns::UpdateDnsRecordParams<'a>,
    api_client: &ApiClientType,
) -> Result<dns::DnsRecord> {
    let response = api_client
        .request(&dns::UpdateDnsRecord {
            zone_identifier,
            identifier,
            params,
        })
        .await;
    match response {
        Ok(res) => Ok(res.result),
        Err(err) => bail!(err),
    }
}

fn send_mail(from: &str, to: &str, subject: &str, body: &str) -> Result<smtp::response::Response> {
    let email = Message::builder()
        .from(from.parse()?)
        .to(to.parse()?)
        .subject(subject)
        .body(body.to_owned())?;

    // Open a local connection on port 25 and send the email
    let mailer = SmtpTransport::unencrypted_localhost();

    mailer
        .send(&email)
        .map_err(|e| anyhow!("Failed to send email: {}", e))
}
