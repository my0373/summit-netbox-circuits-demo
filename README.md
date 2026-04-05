# Red Hat Summit 2026 — NetBox Circuits Demo

Automated circuit failover driven by NetBox as the source of truth, built for Red Hat Summit 2026.

A global enterprise runs WAN circuits between its UK hub (GB-Bristol) and a regional office in Atlanta (US-Atlanta). The primary circuit goes down. With NetBox and AAP, the entire failover — router reconfiguration, CMDB update, and incident report — happens in seconds with no manual intervention.

## Demo Flow

### 1. Set the scene

Open **NetBox Visual Explorer** and show the live topology. All circuits are active and the map shows full connectivity between GB-Bristol and US-Atlanta.

### 2. Trigger the failure

Tell **NetBox Copilot**:

> "IPLC-GB-AT-PRI has failed — set it to offline"

Copilot PATCHes the circuit status to `offline` via the NetBox API.

### 3. Automation kicks in

The status change fires a **NetBox event rule**, which sends a webhook to AAP launching the **Circuit Failover Workflow**. Watch the workflow run in the AAP UI.

**Step 1 — Circuit Failover** (`pb_circuit_failover.yml`):

- Queries NetBox for the failed circuit and resolves its A-side (GB-Bristol) and Z-side (US-Atlanta) sites from circuit terminations
- Finds all active circuits with the `dd` tag present at both sites
- Selects the best backup by committed bandwidth
- Simulates pushing a failover routing config to routers at both ends (stub — no real devices in the demo)
- PATCHes NetBox: primary circuit → `offline`, backup circuit → `active`

**Step 2 — Deploy Report** (`pb_deploy_report.yml`):

- Re-queries NetBox for the current circuit state
- Generates an HTML incident report from a Jinja2 template
- Deploys the report to the report web server over SSH

### 4. Watch the map update

Return to **Visual Explorer**. The failed circuit has disappeared from the map and the backup is now shown as active. The topology updated live as AAP wrote back to NetBox.

### 5. Open the incident report

Open the report URL:

```
https://13.41.146.206/failover_report.html
```

The report shows the full incident summary: which circuit failed, which backup was selected, committed bandwidth, router config changes, and timestamps.

### 6. Confirm with Claude via MCP

Ask Claude (connected to NetBox via the MCP server):

> "What is the current status of IPLC-GB-AT-PRI?"

Claude queries NetBox directly through the MCP server and confirms the circuit is offline and the backup is active — no UI needed.

---

## Key Points

- **NetBox is the trigger, not a passive CMDB.** One status change in Copilot kicks off the entire automation chain.
- **No hardcoded backup mappings.** The playbook discovers the backup dynamically from NetBox. Add a new circuit and it's automatically a candidate next time.
- **Two-step workflow.** Circuit update and report deployment are separate, auditable steps — visible in AAP's job history.
- **Visual Explorer updates live.** The map reflects the new topology immediately after AAP writes back.
- **The MCP server confirms it.** Claude can query NetBox directly at the end to confirm circuit status — no UI required.

---

## Infrastructure

| Component | Details |
|---|---|
| NetBox Cloud | `ryvr4514.cloud.netboxapp.com` — circuits, devices, Visual Explorer, Copilot, webhooks |
| AAP Controller | `netbox-aap25.demoredhat.com` — workflow, job templates, project, inventory |
| Report server | AWS EC2 t3.micro (eu-west-2), nginx HTTPS, SSH on port 2222 |
| MCP server | AWS EC2 t3.micro (eu-west-2), netboxlabs/netbox-mcp-server, SSH stdio |

---

## Setup

### Prerequisites

- Python 3.11+ with `uv`
- Ansible and `ansible-navigator`
- AWS CLI configured for `eu-west-2`
- Terraform

### First-time setup

```bash
cp .env.example .env
# fill in .env with your credentials

uv run --with requests python setup_aap.py   # creates AAP job templates, workflow, credentials, and NetBox webhook/event rule

./setup_infra.sh                             # provisions EC2 instances with Terraform

./reset.sh                                   # sets all dd-tagged circuits to active, ready to demo
```

### Running the demo

Follow the Demo Flow above. To reset between runs:

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
| `NETBOX_URL` | NetBox Cloud instance URL |
| `NETBOX_TOKEN` | NetBox API token |
| `AAP_URL` | AAP Controller base URL |
| `AAP_USERNAME` | AAP username |
| `AAP_PASSWORD` | AAP password |
| `AAP_TOKEN` | AAP OAuth token — used by the NetBox webhook to launch the workflow |

`.env` is gitignored and will never be committed.

---

## Repository layout

```
ansible/
  pb_circuit_failover.yml   # Step 1: find backup, update NetBox
  pb_deploy_report.yml      # Step 2: generate and publish HTML report
  pb_reset_demo.yml         # Reset all dd-tagged circuits to active
  templates/
    failover_report.html.j2 # Jinja2 HTML report template
  vars/
    netbox_creds.yml        # Generated by setup.sh (gitignored)
    infra.yml               # Generated by setup_infra.sh (gitignored)
infra/
  main.tf                   # Terraform — EC2 report server + MCP server
rulebooks/                  # Legacy EDA rulebooks (not used — see eda_fail.md)
setup_aap.py                # Idempotent AAP + NetBox configuration script
setup.sh / reset.sh         # Helper scripts
DEMO.md                     # Full scenario and architecture reference
eda_fail.md                 # Why EDA was abandoned in favour of direct webhooks
```
