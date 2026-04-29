# Setup Guide

## Prerequisites

- **Ansible Automation Platform 2.6** — containerized deployment (all-in-one or growth topology)
- **NetBox** — NetBox Cloud or self-hosted instance with Visual Explorer and Copilot
- `ansible-navigator` and `ansible-rulebook`
- AWS CLI configured for `eu-west-2` (for report/MCP server infrastructure)
- Terraform
- Podman (for local testing)

---

## Environment Variables

Copy `.env.example` to `.env` and fill in:

| Variable | Description |
|---|---|
| `NETBOX_URL` | NetBox instance URL |
| `NETBOX_TOKEN` | NetBox API token (v1 format required — see note below) |
| `AAP_URL` | Ansible Automation Platform base URL |
| `AAP_USERNAME` | AAP username |
| `AAP_PASSWORD` | AAP password |
| `AAP_TOKEN` | AAP OAuth token — used by the NetBox webhook to launch the workflow |
| `EDA_STREAM_TOKEN` | Shared token for NetBox → EDA webhook authentication (any strong random string) |

`.env` is gitignored and will never be committed.

**NetBox v4.5 token note:** NetBox v4.5+ defaults to v2 API tokens, which are not compatible with the `netbox.netbox` Ansible collection. When creating a token, explicitly request v1 format via the provisioning API or select v1 in the NetBox UI.

---

## Ansible Automation Platform Configuration

AAP 2.6 requires the following resources configured. The `pb_setup_aap.yml` playbook creates all of these automatically.

### Automation Controller

| Resource | Name | Details |
|---|---|---|
| Organization | Summit | All resources scoped to this org |
| Project | Summit NetBox Circuits Demo | Git source — this repository, synced on launch |
| Inventory | Summit Demo - Localhost | Localhost + report server hosts |
| Credential | NetBox Cloud - Summit Demo | NetBox credential type — injects `NETBOX_API` + `NETBOX_TOKEN` |
| Credential | Summit Demo Report Server SSH | Machine credential for report server (SSH key) |
| Job Template | Circuit Failover | Runs `ansible/pb_circuit_failover.yml`, accepts `failed_circuit` extra var |
| Job Template | Deploy Report | Runs `ansible/pb_deploy_report.yml`, accepts `failed_circuit` extra var |
| Job Template | Reset Demo | Runs `ansible/pb_reset_demo.yml` |
| Workflow Template | Circuit Failover Workflow | Step 1: Circuit Failover → (on success) → Step 2: Deploy Report |

### Execution Environment

The Controller job templates require an Execution Environment with:
- `netbox.netbox` collection (>= 3.22.0)
- `pynetbox` Python library

### Event-Driven Ansible

| Resource | Name | Details |
|---|---|---|
| Decision Environment | Summit Demo DE | `registry.redhat.io/ansible-automation-platform-26/de-supported-rhel9:latest` |
| Project | Summit NetBox Circuits Demo | Same Git repository — EDA discovers `rulebooks/rulebook.yml` |
| Credential | AAP Controller - Summit Demo | EDA credential for `run_workflow_template` action |
| Credential | NetBox Webhook Token | Token Event Stream credential for webhook authentication |
| Event Stream | NetBox Circuit Events | HTTP endpoint that receives NetBox circuit change webhooks |
| Rulebook Activation | NetBox Circuit Failover | Runs `rulebook.yml` with the DE, listens for NetBox events |

The EDA rulebook activation receives webhooks from NetBox via the event stream, evaluates the circuit status condition, and launches the Circuit Failover Workflow on Automation Controller.

### NetBox Integration

| Resource | Details |
|---|---|
| Webhook | Posts to the EDA event stream endpoint (or directly to the AAP workflow launch URL as fallback) |
| Event Rule | Fires on `circuits.circuit` `object_updated` events, triggers the webhook |

**Webhook body template:** Use an empty body template (NetBox default payload). Custom `body_template` with `{{ data | tojson }}` fails on NetBox v4.5 due to Django lazy proxy serialization.

---

## First-Time Setup

```bash
# 1. Initial setup — creates .env and ansible/vars/infra.yml placeholders
./setup.sh
# Fill in .env with your NetBox, AAP, and EDA credentials

# 2. Install required Ansible collections
ansible-galaxy collection install -r collections/requirements.yml

# 3. Configure AAP, EDA, and NetBox resources (idempotent — safe to re-run)
source .env
./run-playbook.sh ansible/pb_setup_aap.yml

# 4. Provision AWS infrastructure (report server + MCP server)
# This also re-runs pb_setup_aap.yml with report server registration
./setup_infra.sh

# 5. Reset circuits to starting state
./reset.sh
```

All AAP, EDA, and NetBox resources are created by `pb_setup_aap.yml` using the `ansible.controller`, `ansible.eda`, and `netbox.netbox` collections. No Python dependencies required.

---

## Running Playbooks

### With ansible-navigator (recommended)

```bash
ansible-navigator run ansible/pb_circuit_failover.yml \
  -i ansible/inventory/localhost.yml \
  --eei <your-ee-image> \
  --mode stdout --penv NETBOX_URL --penv NETBOX_TOKEN
```

### With the wrapper script

```bash
# Sources .env and runs ansible-playbook directly
./run-playbook.sh ansible/pb_circuit_failover.yml
./run-playbook.sh ansible/pb_deploy_report.yml --extra-vars "failed_circuit=IPLC-GB-AT-PRI"
```

### Resetting between demo runs

```bash
./reset.sh
```

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
