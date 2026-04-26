# Red Hat Summit 2026 — NetBox Circuits Demo

Automated circuit failover driven by NetBox as the source of truth, built for Red Hat Summit 2026.

A global enterprise runs WAN circuits between its UK hub (GB-Bristol) and a regional office in Atlanta (US-Atlanta). The primary circuit goes down. With NetBox and Ansible Automation Platform, the entire failover — router reconfiguration, CMDB update, and incident report — happens in under 30 seconds with no manual intervention.

## Demo Flow

### 1. Set the scene

Open **NetBox Visual Explorer** and show the live topology. All circuits are active and the map shows full connectivity between GB-Bristol and US-Atlanta.

### 2. Trigger the failure

Tell **NetBox Copilot**:

> "IPLC-GB-AT-PRI has failed — set it to offline"

Copilot PATCHes the circuit status to `offline` via the NetBox API.

### 3. Automation kicks in

The status change fires a **NetBox event rule**. Event-Driven Ansible detects the circuit update and triggers the **Circuit Failover Workflow** in Ansible Automation Platform.

**Step 1 — Circuit Failover** (`pb_circuit_failover.yml`):

- Queries NetBox for the failed circuit using `netbox.netbox.nb_lookup` and resolves its A-side (GB-Bristol) and Z-side (US-Atlanta) sites from circuit terminations
- Finds all circuits with the `dd` tag present at both sites
- Selects the best backup by committed bandwidth
- Pushes failover routing config to routers at both ends
- Updates NetBox via `netbox.netbox.netbox_circuit`: primary → `offline`, backup → `active`

**Step 2 — Deploy Report** (`pb_deploy_report.yml`):

- Re-queries NetBox for the current circuit state
- Generates an HTML incident report with topology diagram, bandwidth impact, failover timeline, audit trail, and recommended next steps
- Deploys the report to the report web server over SSH

### 4. Watch the map update

Return to **Visual Explorer**. The failed circuit has disappeared from the map and the backup is now shown as active. The topology updated live as Ansible Automation Platform wrote back to NetBox.

### 5. Open the incident report

Open the report URL served by the report web server. The report shows the full incident summary: topology diagram, which circuit failed, which backup was selected, bandwidth capacity impact, router config changes, failover timeline with step-by-step timestamps, and links to the NetBox audit trail.

### 6. Confirm with Claude via MCP

Ask Claude (connected to NetBox via the MCP server):

> "What is the current status of IPLC-GB-AT-PRI?"

Claude queries NetBox directly through the MCP server and confirms the circuit is offline and the backup is active — no UI needed.

---

## Key Points

- **NetBox is the trigger, not a passive CMDB.** One status change in Copilot kicks off the entire automation chain via Event-Driven Ansible.
- **No hardcoded backup mappings.** The playbook discovers the backup dynamically from NetBox using the `netbox.netbox` collection. Add a new circuit and it's automatically a candidate next time.
- **Two-step workflow.** Circuit update and report deployment are separate, auditable steps — visible in Ansible Automation Platform's job history.
- **Visual Explorer updates live.** The map reflects the new topology immediately after Ansible Automation Platform writes back.
- **The MCP server confirms it.** Claude can query NetBox directly at the end to confirm circuit status — no UI required.

---

## Infrastructure

| Component | Details |
|---|---|
| NetBox | Your NetBox instance — circuits, devices, Visual Explorer, Copilot, webhooks |
| Ansible Automation Platform | Your AAP instance — workflow, job templates, project, inventory |
| Report server | AWS EC2 t3.micro (eu-west-2), nginx HTTPS, SSH on port 2222 |
| MCP server | AWS EC2 t3.micro (eu-west-2), netboxlabs/netbox-mcp-server, SSH stdio |

---

## Setup

### Prerequisites

- Python 3.12+ with `uv`
- Ansible, `ansible-navigator`, and the `netbox.netbox` collection (see `collections/requirements.yml`)
- AWS CLI configured for `eu-west-2`
- Terraform
- Podman (for local testing)

### First-time setup

```bash
cp .env.example .env
# fill in .env with your NetBox and AAP credentials

# Install the netbox.netbox collection
ansible-galaxy collection install -r collections/requirements.yml

# Configure AAP job templates, workflow, credentials, and NetBox webhook/event rule
uv run --with requests python setup_aap.py

# Provision EC2 instances (report server + MCP server)
./setup_infra.sh

# Reset circuits to starting state
./reset.sh
```

### Running playbooks locally

```bash
# All playbooks use ansible-navigator with your execution environment:
ansible-navigator run ansible/pb_circuit_failover.yml \
  -i ansible/inventory/localhost.yml \
  --eei <your-ee-image> \
  --mode stdout --penv NETBOX_URL --penv NETBOX_TOKEN

# Or use the wrapper script (sources .env, runs ansible-playbook directly):
./run-playbook.sh ansible/pb_circuit_failover.yml
./run-playbook.sh ansible/pb_deploy_report.yml --extra-vars "failed_circuit=IPLC-GB-AT-PRI"
```

### Resetting between demo runs

```bash
./reset.sh
```

### Tearing down infrastructure

```bash
./teardown_infra.sh
```

---

## Environment variables

Copy `.env.example` to `.env` and fill in:

| Variable | Description |
|---|---|
| `NETBOX_URL` | NetBox instance URL |
| `NETBOX_TOKEN` | NetBox API token (v1 format for compatibility) |
| `AAP_URL` | Ansible Automation Platform base URL |
| `AAP_USERNAME` | AAP username |
| `AAP_PASSWORD` | AAP password |
| `AAP_TOKEN` | AAP OAuth token — used by the NetBox webhook to launch the workflow |

`.env` is gitignored and will never be committed.

---

## Demo Circuits

| CID | Role | Starting State |
|---|---|---|
| `IPLC-GB-AT-PRI` | Primary (fails in demo) | active |
| `IPLC-GB-AT-SEC` | Backup (activated by automation) | offline |

All demo circuits are tagged `dd` in NetBox. This tag scopes all queries — backup discovery, reset, and report generation only touch `dd`-tagged objects.

---

## Repository layout

```
ansible/
  pb_circuit_failover.yml   # Step 1: find backup, update NetBox (netbox.netbox collection)
  pb_deploy_report.yml      # Step 2: generate and publish HTML report
  pb_reset_demo.yml         # Reset all dd-tagged circuits to starting state
  pb_seed_netbox.yml        # Seed a fresh NetBox instance with demo data
  pb_setup_local_netbox.yml # Deploy local NetBox via Podman for testing
  templates/
    failover_report.html.j2 # Jinja2 HTML report template
  vars/
    netbox_creds.yml        # Credentials via env vars (works with AAP injection)
  inventory/
    localhost.yml            # Localhost inventory for local execution
collections/
  requirements.yml          # netbox.netbox collection dependency
infra/
  main.tf                   # Terraform — EC2 report server + MCP server
rulebooks/
  rulebook.yml              # EDA rulebook for Event-Driven Ansible integration
setup_aap.py                # Idempotent AAP + NetBox configuration script
setup.sh / reset.sh         # Helper scripts
DEMO.md                     # Full scenario and architecture reference
eda_fail.md                 # Why direct webhooks are used instead of EDA event streams
```
