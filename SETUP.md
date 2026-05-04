# Setup Guide

## Prerequisites

- **Ansible Automation Platform 2.6** — containerized deployment (all-in-one or growth topology)
- **NetBox** — NetBox Cloud or self-hosted instance with Visual Explorer and Copilot
- `ansible-navigator` (all playbooks run inside the project Execution Environment)
- Podman or Docker (container engine for ansible-navigator)
- AWS CLI configured for `eu-west-2` (for report/MCP server infrastructure)
- Terraform (for infrastructure provisioning)
- Podman (for local testing)

---

## Environment Variables

Copy `.env.example` to `.env` and fill in:

| Variable | Required | Description |
|---|---|---|
| `NETBOX_URL` | Yes | NetBox instance URL |
| `NETBOX_TOKEN` | Yes | NetBox API token (v1 format required — see note below) |
| `AAP_URL` | Yes | Ansible Automation Platform base URL |
| `AAP_USERNAME` | Yes | AAP username |
| `AAP_PASSWORD` | Yes | AAP password |
| `AAP_TOKEN` | Yes | AAP OAuth token — used by the NetBox webhook to launch the workflow |
| `EDA_STREAM_TOKEN` | Yes | Shared token for NetBox → EDA webhook authentication (any strong random string) |
| `REGISTRY_HOST` | No | Container registry host for EE images (default: `quay.io`) |
| `REGISTRY_USERNAME` | No | Registry username (omit for public images) |
| `REGISTRY_PASSWORD` | No | Registry password |
| `RH_REGISTRY_USERNAME` | No | Red Hat Customer Portal username — for pulling DE image from `registry.redhat.io` if not already present on AAP |
| `RH_REGISTRY_PASSWORD` | No | Red Hat Customer Portal password |
| `AH_URL` | No | Automation Hub URL (default: `https://console.redhat.com/api/automation-hub/`) |
| `AH_TOKEN` | No | Automation Hub token |
| `REPORT_SERVER_HOST` | No | IP or hostname of the report web server |
| `REPORT_SERVER_PORT` | No | SSH port for report server (default: `2222`) |
| `REPORT_URL` | No | Public URL where the report is served (derived automatically if empty) |
| `ROUTER_IP` | No | Management IP of the Cisco router |
| `ROUTER_PASSWORD` | No | Password for the router Network credential |
| `ROUTER_USERNAME` | No | Router username (default: `iosuser`) |
| `ROUTER_PRIMARY_GW` | No | Primary circuit gateway IP (default: `172.16.0.1`) |
| `ROUTER_BACKUP_GW` | No | Backup circuit gateway IP (default: `172.16.1.1`) |
| `PRIVATE_KEY_PATH` | No | Absolute path to SSH private key for infrastructure VMs |

`.env` is gitignored and will never be committed.

**NetBox v4.5 token note:** NetBox v4.5+ defaults to v2 API tokens, which are not compatible with the `netbox.netbox` Ansible collection. When creating a token, explicitly request v1 format via the provisioning API or select v1 in the NetBox UI.

---

## Ansible Automation Platform Configuration

AAP 2.6 requires the following resources configured. The `pb_setup_aap.yml` playbook creates all of these automatically.

### Automation Controller

All resources are scoped to the `SummitCollection` organization (configurable via `aap_org_name` in `pb_setup_aap.yml`).

| Resource | Name | Details |
|---|---|---|
| Credential | SummitCollection NetBox Cloud | NetBox credential type — injects `NETBOX_API` + `NETBOX_TOKEN` |
| Credential | SummitCollection Container Registry | Quay.io registry for pulling the project EE image |
| Credential | SummitCollection Automation Hub | Galaxy/Automation Hub for certified collections |
| Credential | SummitCollection Report Server SSH | Machine credential for report server (SSH key, conditional) |
| Credential | SummitCollection Network Router | Network credential for Cisco router (conditional) |
| Inventory | SummitCollection Localhost | Localhost + report server hosts |
| Project | SummitCollection NetBox Circuits Demo | Git source — this repository, synced on launch |
| Execution Environment | SummitCollection Execution Environment | `quay.io/acme_corp/netbox-summit-2026-ee:v3.22` |
| Job Template | SummitCollection Circuit Failover | Runs `pb_circuit_failover.yml`, accepts `failed_circuit` extra var |
| Job Template | SummitCollection Deploy Report | Runs `pb_deploy_report.yml`, accepts `failed_circuit` extra var |
| Job Template | SummitCollection Reset Demo | Runs `pb_reset_demo.yml` |
| Workflow Template | SummitCollection Circuit Failover Workflow | Step 1: Circuit Failover → (on success) → Step 2: Deploy Report |

### Execution Environment

The project EE (`quay.io/acme_corp/netbox-summit-2026-ee:v3.22`) includes all required collections and Python dependencies:
- `netbox.netbox` >= 3.22.0, `ansible.controller`, `ansible.eda`
- `cisco.ios`, `ansible.netcommon`, `ansible.utils`
- `pynetbox` >= 7.6.0

The same EE is used for both local runs (via `ansible-navigator.yml`) and AAP job templates.

### Event-Driven Ansible

| Resource | Name | Details |
|---|---|---|
| Decision Environment | SummitCollection Decision Environment | `registry.redhat.io/ansible-automation-platform-26/de-supported-rhel9:latest` (pull policy: missing) |
| Credential | SummitCollection Red Hat Registry | Container Registry credential for `registry.redhat.io` (optional — only needed if DE image not present) |
| Project | SummitCollection EDA Project | Same Git repository — EDA discovers `rulebooks/rulebook.yml` |
| Credential | SummitCollection EDA AAP Controller | EDA credential for `run_workflow_template` — host must include `/api/controller` path for AAP 2.6 gateway |
| Credential | SummitCollection EDA Webhook Token | Token Event Stream credential for webhook authentication |
| Event Stream | SummitCollection EDA Circuit Events | HTTP endpoint that receives NetBox circuit change webhooks |
| Rulebook Activation | SummitCollection EDA Circuit Failover | Runs `rulebook.yml` with the DE, listens for NetBox events |

The EDA rulebook activation receives webhooks from NetBox via the event stream, evaluates the circuit status condition, and launches the Circuit Failover Workflow on Automation Controller.

**AAP 2.6 gateway note:** The EDA AAP Controller credential `host` must be set to `https://<aap-host>/api/controller` (not just the base URL). The AAP 2.6 unified gateway routes controller API requests through `/api/controller/v2/`.

### NetBox Integration

| Resource | Details |
|---|---|
| Webhook | Posts to the EDA event stream endpoint (or directly to the AAP workflow launch URL as fallback) |
| Event Rule | Fires on `circuits.circuit` `object_updated` events, triggers the webhook |

**Webhook body template:** Use an empty body template (NetBox default payload). Custom `body_template` with `{{ data | tojson }}` fails on NetBox v4.5 due to Django lazy proxy serialization.

---

## First-Time Setup

```bash
# 1. Initial setup — creates .env from .env.example
./setup.sh
# Fill in .env with your NetBox, AAP, and EDA credentials
```

All collections are bundled in the project EE — no `ansible-galaxy install` needed. All AAP, EDA, and NetBox resources are created by `pb_setup_aap.yml`.

### Option A: With Terraform (full demo with AWS infrastructure)

Provisions EC2 instances for the report server and Cisco router, then configures AAP with all resources including infrastructure hosts.

```bash
# 3. Provision AWS infrastructure — populates .env with infra variables
./setup_infra.sh

# 4. Reset circuits to starting state
./reset.sh
```

`setup_infra.sh` runs Terraform, writes the resulting IPs and credentials to `.env`, and re-runs `pb_setup_aap.yml` to register the infrastructure in AAP.

### Option B: Without Terraform (AAP + NetBox only)

The core demo works without AWS infrastructure. Report publishing and router configuration are skipped gracefully when their variables are empty in `.env`.

```bash
# 3. (Optional) Fill in infrastructure variables in .env
#    Leave REPORT_SERVER_HOST, ROUTER_IP, etc. empty to skip those features

# 4. Configure AAP, EDA, and NetBox resources
./run-playbook.sh ansible/pb_setup_aap.yml

# 5. Reset circuits to starting state
./reset.sh
```

When an infrastructure variable is empty:
- **No `REPORT_SERVER_HOST`** — report is generated locally but not published to a web server
- **No `ROUTER_IP`** — router credential and NetBox device IP registration are skipped

---

## Running Playbooks

All playbooks run inside the project EE via `ansible-navigator`. The `ansible-navigator.yml` config handles the EE image, env injection (via `--env-file .env`), and output mode.

```bash
# Using the wrapper script (recommended)
./run-playbook.sh ansible/pb_circuit_failover.yml
./run-playbook.sh ansible/pb_deploy_report.yml --extra-vars "failed_circuit=IPLC-GB-AT-PRI"
./run-playbook.sh ansible/pb_setup_aap.yml

# Reset between demo runs
./reset.sh
```

To override the EE image, set `EE_IMAGE` before running or edit `ansible-navigator.yml`.

---

## Local Testing (without AAP)

Deploy a local NetBox instance and EDA environment for testing the playbooks and rulebook without an AAP instance.

### Deploy local NetBox

```bash
# Start NetBox on port 8001 via Podman, creates admin user and .env
ansible-playbook ansible/pb_setup_local_netbox.yml

# Seed demo data (sites, circuits, routers, terminations)
./run-playbook.sh ansible/pb_seed_netbox.yml
```

### Test EDA rulebook

```bash
# Start ansible-rulebook in AAP 2.6 DE with debug action (no AAP needed)
./run-playbook.sh ansible/pb_setup_local_eda.yml -e test=true

# Watch EDA logs in one terminal
podman logs -f eda-rulebook

# Trigger a circuit failure — watch EDA pick it up
curl -s -X PATCH "http://localhost:8001/api/circuits/circuits/1/" \
  -H "Authorization: Token <your-token>" \
  -H "Content-Type: application/json" \
  -d '{"status": "offline"}'
```

### Run the full playbook cycle

```bash
./run-playbook.sh ansible/pb_reset_demo.yml
# Set IPLC-GB-AT-PRI to offline in NetBox, then:
./run-playbook.sh ansible/pb_circuit_failover.yml
./run-playbook.sh ansible/pb_deploy_report.yml -e "failed_circuit=IPLC-GB-AT-PRI"
```

### Teardown

```bash
./run-playbook.sh ansible/pb_setup_local_eda.yml -e teardown=true
ansible-playbook ansible/pb_setup_local_netbox.yml -e teardown=true
./teardown_infra.sh  # AWS resources
```

---

## MCP Servers

### NetBox MCP Server

Provides Claude with direct access to NetBox data via the Model Context Protocol. Runs on an EC2 instance, communicates over SSH stdio.

Example queries during the demo:
- "What is the current status of IPLC-GB-AT-PRI?"
- "Which circuits connect GB-Bristol and US-Atlanta?"
- "Show me all active circuits tagged dd"

### AAP MCP Server

Provides Claude with access to Ansible Automation Platform job and workflow data. Enables the presenter to query automation execution history conversationally.

Example queries during the demo:
- "Show me the last workflow job that ran"
- "What was the result of the Circuit Failover job?"
- "How long did the failover workflow take to complete?"
- "What extra variables were passed to the last Circuit Failover run?"
- "Are there any failed jobs in the last hour?"

Together, the two MCP servers let Claude confirm both the **state of the network** (via NetBox) and the **actions taken by automation** (via AAP) — closing the loop without touching any UI.
