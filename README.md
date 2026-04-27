# Red Hat Summit 2026 — NetBox Circuits Demo

Automated WAN circuit failover driven by **NetBox** as the Source of Truth and **Red Hat Ansible Automation Platform 2.6** as the automation engine, built for Red Hat Summit 2026.

A global enterprise runs WAN circuits between its UK hub (GB-Bristol) and a regional office in Atlanta (US-Atlanta). The primary circuit goes down. With NetBox, Event-Driven Ansible, and Ansible Automation Platform, the entire failover — router reconfiguration, CMDB update, and incident report — happens in under 30 seconds with no manual intervention.

## Demo Flow

### 1. Set the scene

Open **NetBox Visual Explorer** and show the live topology. All circuits are active and the map shows full connectivity between GB-Bristol and US-Atlanta. Optionally, show the **Ansible Automation Platform** dashboard — the Circuit Failover Workflow is idle, waiting for events.

### 2. Trigger the failure

Tell **NetBox Copilot**:

> "IPLC-GB-AT-PRI has failed — set it to offline"

Copilot PATCHes the circuit status to `offline` via the NetBox API.

### 3. Event-Driven Ansible detects the change

The status change fires a **NetBox event rule** which sends a webhook. **Event-Driven Ansible** receives the event, evaluates the rulebook condition (circuit status is `offline` or `failed`), and automatically launches the **Circuit Failover Workflow** in Ansible Automation Platform — passing the circuit CID as an extra variable.

Switch to the **AAP UI** and show the workflow running in real time.

### 4. Ansible Automation Platform executes the workflow

**Workflow Step 1 — Circuit Failover** (`pb_circuit_failover.yml`):

- Queries NetBox for the failed circuit using the `netbox.netbox` Ansible collection and resolves its A-side (GB-Bristol) and Z-side (US-Atlanta) sites from circuit terminations
- Discovers all backup candidates with the `dd` tag present at both sites
- Selects the best backup by committed bandwidth (10 Gbps primary → 5 Gbps backup)
- Pushes failover routing config to routers at both ends
- Updates NetBox via `netbox.netbox.netbox_circuit`: primary → `offline`, backup → `active`

**Workflow Step 2 — Deploy Report** (`pb_deploy_report.yml`):

- Re-queries NetBox for the current circuit state
- Generates an HTML incident report with topology diagram, bandwidth impact, failover timeline, audit trail, and recommended next steps
- Deploys the report to the report web server over SSH

### 5. Watch the map update

Return to **Visual Explorer**. The failed circuit has disappeared from the map and the backup is now shown as active. The topology updated live as Ansible Automation Platform wrote back to NetBox.

### 6. Open the incident report

Open the report URL served by the report web server. The report shows the full incident summary: network topology SVG, which circuit failed, which backup was selected, bandwidth capacity degradation (50%), router config changes, a step-by-step failover timeline with timestamps showing each AAP workflow step, and direct links to the NetBox audit trail.

### 7. Confirm with Claude via MCP

Ask Claude (connected to NetBox and AAP via MCP servers):

> "What is the current status of IPLC-GB-AT-PRI?"

Claude queries NetBox directly through the **NetBox MCP server** and confirms the circuit is offline and the backup is active.

> "Show me the last workflow job that ran"

Claude queries AAP through the **AAP MCP server** and shows the workflow execution details — job status, timestamps, which playbooks ran, and the extra variables that were passed.

### 8. Reset for the next run

Run `./reset.sh` or launch the **Reset Demo** job template in AAP to restore all circuits to their starting state.

---

## Key Points

- **NetBox is the trigger, not a passive CMDB.** One status change in Copilot kicks off the entire automation chain via Event-Driven Ansible.
- **Event-Driven Ansible bridges NetBox and AAP.** The EDA rulebook listens for circuit events and launches the right workflow automatically — no polling, no manual intervention.
- **No hardcoded backup mappings.** The playbook discovers the backup dynamically from NetBox using the `netbox.netbox` collection. Add a new circuit and it's automatically a candidate next time.
- **Two-step workflow in AAP.** Circuit update and report deployment are separate, auditable steps — visible in Ansible Automation Platform's job history with full logs and timing.
- **Visual Explorer updates live.** The map reflects the new topology immediately after Ansible Automation Platform writes back.
- **MCP servers close the loop.** Claude can query both NetBox (circuit status) and AAP (job execution history) directly — no UI required.

---

## Infrastructure

| Component | Details |
|---|---|
| NetBox | NetBox instance — circuits, devices, Visual Explorer, Copilot, event rules |
| Ansible Automation Platform 2.6 | Containerized (all-in-one or growth topology) — Automation Controller, Event-Driven Ansible, workflows, job templates |
| Report server | AWS EC2 t3.micro (eu-west-2), nginx HTTPS, SSH on port 2222 |
| NetBox MCP server | AWS EC2 t3.micro (eu-west-2), netboxlabs/netbox-mcp-server, SSH stdio |
| AAP MCP server | Ansible Automation Platform MCP server — queries jobs, workflows, inventories |

---

## Demo Circuits

| CID | Role | Starting State |
|---|---|---|
| `IPLC-GB-AT-PRI` | Primary (fails in demo) | active |
| `IPLC-GB-AT-SEC` | Backup (activated by automation) | offline |

All demo circuits are tagged `dd` in NetBox. This tag scopes all queries — backup discovery, reset, and report generation only touch `dd`-tagged objects.

---

## Setup

See [SETUP.md](SETUP.md) for full setup instructions including AAP configuration, NetBox integration, and local testing.

---

## Repository layout

```
ansible/
  pb_circuit_failover.yml   # Workflow Step 1: find backup, update NetBox
  pb_deploy_report.yml      # Workflow Step 2: generate and publish HTML report
  pb_reset_demo.yml         # Reset all dd-tagged circuits to starting state
  pb_seed_netbox.yml        # Seed a fresh NetBox instance with demo data
  pb_setup_local_netbox.yml # Deploy local NetBox via Podman for testing
  pb_setup_local_eda.yml    # Deploy local EDA environment for testing
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
  rulebook.yml              # EDA rulebook for Event-Driven Ansible
setup_aap.py                # Idempotent AAP + NetBox configuration script
setup.sh / reset.sh         # Helper scripts
DEMO.md                     # Full scenario and architecture reference
SETUP.md                    # Setup and configuration guide
```
