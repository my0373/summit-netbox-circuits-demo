# Red Hat Summit 2026 — NetBox Circuits Demo

Automated circuit failover driven by NetBox as the source of truth, built for Red Hat Summit 2026.

A global enterprise runs WAN circuits between its UK hub (GB-Bristol) and a regional office in Atlanta (US-Atlanta). The primary circuit goes down. With NetBox and AAP, the entire failover — real router reconfiguration, CMDB update, and incident report — happens in seconds with no manual intervention.

## Demo Flow

### 1. Set the scene

Open **NetBox Visual Explorer** and show the live topology. All circuits are active and the map shows full connectivity between GB-Bristol and US-Atlanta.

### 2. Trigger the failure

Tell **NetBox Copilot**:

> "IPLC-GB-AT-PRI has failed — set it to offline"

Copilot PATCHes the circuit status to `offline` via the NetBox API.

### 3. Automation kicks in

The status change fires a **NetBox event rule**, which sends a webhook to the EDA event stream. EDA's rulebook triggers the **Circuit Failover Workflow** in AAP. Watch the workflow run in the AAP UI.

**Step 1 — Circuit Failover** (`pb_circuit_failover.yml`):

- Queries NetBox for the failed circuit and resolves its A-side (GB-Bristol) and Z-side (US-Atlanta) sites from circuit terminations
- Finds all active circuits with the `dd` tag present at both sites
- Selects the best backup by committed bandwidth
- Pushes a real failover routing config to `gb-brs-rtr-01` (Cisco C8000V EC2 instance) via `cisco.ios.ios_config`
- PATCHes NetBox: primary circuit → `offline`, backup circuit → `active`

**Step 2 — Deploy Report** (`pb_deploy_report.yml`):

- Re-queries NetBox for the current circuit state
- Generates an HTML incident report from a Jinja2 template
- Deploys the report to the report web server over SSH

### 4. Watch the map update

Return to **Visual Explorer**. The failed circuit has disappeared from the map and the backup is now shown as active. The topology updated live as AAP wrote back to NetBox.

### 5. Open the incident report

Open the report URL shown in `ansible/vars/infra.yml` (populated by `setup_infra.sh`):

```
https://<report_server_ip>/failover_report.html
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
- **Real router config.** Ansible pushes actual IOS commands to a live Cisco C8000V via `cisco.ios.ios_config` — not a simulation.
- **Two-step workflow.** Circuit update and report deployment are separate, auditable steps — visible in AAP's job history.
- **Visual Explorer updates live.** The map reflects the new topology immediately after AAP writes back.
- **The MCP server confirms it.** Claude can query NetBox directly at the end to confirm circuit status — no UI required.

---

## Infrastructure

| Component | Details |
|---|---|
| NetBox Cloud | `app.netboxlabs.com` — circuits, devices, [Visual Explorer](https://app.netboxlabs.com/visual-explorer), Copilot, webhooks |
| AAP 2.5 Controller | `netbox-aap25.demoredhat.com` — workflow, job templates, EDA, credentials |
| EDA | `network-netbox-de` decision environment, `network-netbox-ee-stable` execution environment |
| Report server | AWS EC2 t3.micro (eu-west-2), nginx HTTPS, SSH on port 2222 |
| MCP server | AWS EC2 t3.micro (eu-west-2), netboxlabs/netbox-mcp-server, SSH stdio |
| Cisco router | AWS EC2 c5n.large (eu-west-2), Cisco C8000V IOS-XE — `gb-brs-rtr-01` A-side router |

---

## Setup

### Prerequisites

- Python 3.12+ and `uv`
- Ansible (`brew install ansible` on macOS)
- AWS CLI configured with access to `eu-west-2`
- Terraform
- AWS Marketplace subscription accepted for **Cisco Catalyst 8000V Edge Software** (BYOL) in `eu-west-2` — Terraform discovers the AMI automatically by product code; you just need the subscription active before running `setup_infra.sh`

### First-time setup

```bash
# 1. Initialise — creates .env from template and installs Python deps
./setup.sh

# 2. Fill in .env with your credentials
#    (NETBOX_URL, NETBOX_TOKEN, AAP_URL, AAP_USERNAME, AAP_PASSWORD, EDA_STREAM_TOKEN)

# 3. Configure AAP + EDA (idempotent — safe to re-run)
uv run --with requests python setup_aap.py

# 4. Provision AWS infrastructure (Terraform + VM setup + AAP inventory registration)
#    This also updates gb-brs-rtr-01's primary IP in NetBox to the EC2 Elastic IP
./setup_infra.sh

# 5. Install Ansible collections (first time only)
ansible-galaxy collection install -r ansible/requirements.yml --force

# 6. Reset NetBox circuits to starting state and restore router primary route
./reset.sh
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
| `EDA_STREAM_TOKEN` | Shared token for the EDA event stream (must match what is configured in EDA) |

`.env` is gitignored and will never be committed.

---

## Repository layout

```
ansible/
  pb_circuit_failover.yml   # Step 1: find backup, push router config, update NetBox
  pb_deploy_report.yml      # Step 2: generate and publish HTML report
  pb_reset_demo.yml         # Reset: restore circuits + router primary route
  requirements.yml          # Ansible collection deps (cisco.ios, ansible.netcommon)
  templates/
    failover_report.html.j2 # Jinja2 HTML report template
  vars/
    netbox_creds.yml        # NetBox credentials (env-var driven)
    network_creds.yml       # Router credentials (iosuser/iospass, gateway IPs)
    infra.yml               # Generated by setup_infra.sh (gitignored)
    infra.yml.example       # Placeholder with empty values
infra/
  main.tf                   # Terraform — report server, MCP server, Cisco router EC2
  variables.tf              # Terraform variables
  outputs.tf                # Outputs: IPs, SSH commands, MCP registration command
  userdata.sh.tpl           # Report server cloud-init
  userdata_mcp.sh.tpl       # MCP server cloud-init
  userdata_router.tpl       # Cisco IOS-XE Day 0 bootstrap config
rulebooks/
  rulebook.yml              # EDA rulebook — triggers Circuit Failover Workflow on circuit status change
slides/
  make_deck.py              # Generates Summit_Demo_Deck.pptx
setup_aap.py                # Idempotent AAP + EDA + NetBox configuration script
setup.sh                    # First-time init
setup_infra.sh              # Terraform + VM registration + NetBox router IP update
reset.sh                    # Reset circuits + router route (run between demo attempts)
teardown_infra.sh           # Terraform destroy + cleanup
DEMO.md                     # Full scenario and architecture reference
ansible.cfg                 # Disables SSH host key checking (required for Cisco router)
```
