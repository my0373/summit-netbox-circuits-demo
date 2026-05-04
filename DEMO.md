# Summit Demo — Scenario and Architecture

## The Scenario

A global enterprise runs WAN circuits between its UK hub (GB-Bristol) and regional offices including Atlanta (US-Atlanta). The primary circuit goes down. Without automation, the network team would need to:

- Detect the failure and identify the backup circuit manually
- Log into routers at both ends and reconfigure routing
- Update the CMDB to reflect the new topology
- Brief stakeholders with an incident report

With NetBox as the Source of Truth and Ansible Automation Platform as the automation engine, the entire process takes under 30 seconds and requires no manual intervention beyond telling Copilot what happened.

## The Demo Flow

```
Presenter tells Copilot the circuit has failed
        |
NetBox Copilot sets IPLC-GB-AT-PRI -> offline
        |
NetBox event rule fires -> webhook to Event-Driven Ansible
        |
Event-Driven Ansible evaluates rulebook condition
        |
EDA launches Circuit Failover Workflow on Automation Controller
        |
  Step 1: Circuit Failover playbook (via netbox.netbox collection)
    - Queries NetBox for the failed circuit and its sites
    - Discovers backup circuits between the same sites
    - Selects best backup by committed bandwidth
    - Pushes failover routing config to routers
    - Updates NetBox: primary -> offline, backup -> active
        |
  Step 2: Deploy Report playbook
    - Re-queries NetBox for current circuit state
    - Generates HTML incident report from Jinja2 template
    - Deploys report to the report web server over SSH
        |
Visual Explorer map updates live (failed circuit disappears)
        |
Presenter opens report URL — shows full incident summary
        |
Presenter asks Claude (via NetBox + AAP MCP servers):
  "What is the status of IPLC-GB-AT-PRI?"
  "Show me the last workflow job that ran"
```

## Architecture

```
NetBox                          Ansible Automation Platform 2.6
-----------------               ------------------------------------------
+-----------+                   +--------------------------------------+
|  Copilot  | PATCH circuit     |  Event-Driven Ansible                |
| (AI chat) |--- status -->     |  Rulebook: circuit offline/failed    |
+-----------+   = offline       |  -> launch workflow                  |
                                +------------------+-------------------+
+-----------+                                      |
|  Webhooks |  POST                                v
| + Event   |---- event -->     +--------------------------------------+
|   Rules   |  to EDA           |  Automation Controller               |
+-----------+                   |                                      |
                                |  +-------------------------------+   |
+-----------+                   |  | Step 1: Circuit Failover      |   |
|  Visual   | <- live update    |  |  * Query NetBox (nb_lookup)   |   |
|  Explorer |   (map redraws)   |  |  * Find best backup circuit   |   |
+-----------+                   |  |  * Push router config         |   |
                                |  |  * Update NetBox (netbox_circuit) |
+-----------+                   |  +---------------+---------------+   |
| NetBox MCP| <- status check   |                  | on success        |
|  (Claude) |   at end of demo  |  +---------------v---------------+   |
+-----------+                   |  | Step 2: Deploy Report          |   |
                                |  |  * Re-query NetBox state       |   |
+-----------+                   |  |  * Generate HTML report         |   |
| AAP MCP  | <- job history     |  |  * Deploy to report server     |   |
|  (Claude) |   at end of demo  |  +-------------------------------+   |
+-----------+                   +--------------------------------------+
```

## What the Automation Does

### Step 1 — Circuit Failover (`pb_circuit_failover.yml`)

1. Queries NetBox for the failed circuit CID using `netbox.netbox.nb_lookup`
2. Guards against spurious triggers: if the circuit is not actually offline or failed, the playbook exits cleanly
3. Resolves the A-side and Z-side sites from circuit terminations
4. Queries all `dd`-tagged circuits at both sites
5. Finds circuits present at both ends (excluding the failed one) — these are backup candidates
6. Selects the backup with the highest committed bandwidth
7. Pushes failover routing config to Cisco routers at both sites via `cisco.ios.ios_config` (routers without a management IP in NetBox log a simulated stub instead)
8. Updates NetBox via `netbox.netbox.netbox_circuit`: primary circuit -> offline, backup circuit -> active

### Step 2 — Deploy Report (`pb_deploy_report.yml`)

1. Re-queries NetBox for the current state of the failed circuit and its sites
2. Identifies the now-active backup circuit
3. Queries routers at both sites
4. Renders the HTML failover report with topology diagram, bandwidth impact, timeline, audit trail, and next steps
5. Deploys the report to the report web server via SSH

### Reset (`pb_reset_demo.yml`)

Fetches all circuits tagged `dd`, restores the primary to `active` and the backup to `offline`. Safe to run between demo attempts.

## Key Points to Make During the Demo

- **NetBox is the trigger, not a passive CMDB.** One status change in Copilot kicks off the entire automation chain.
- **Event-Driven Ansible is the event router.** The EDA rulebook listens for NetBox events, evaluates conditions, and launches the right workflow — no polling, no manual trigger.
- **No hardcoded backup mappings.** The playbook discovers the backup dynamically from NetBox using the `netbox.netbox` collection. Add a new circuit in NetBox and it's automatically a candidate next time.
- **Two-step workflow in AAP.** The circuit update and report deployment are separate, auditable steps — visible in Automation Controller's job history with full logs and timing.
- **Visual Explorer updates live.** The map reflects the new topology immediately after Ansible Automation Platform writes back.
- **MCP servers close the loop.** Claude can query both NetBox (circuit status) and AAP (job execution history) directly — confirming what happened without touching any UI.

## Infrastructure

| Component | Details |
|---|---|
| NetBox | NetBox instance — circuits, devices, Visual Explorer, Copilot, event rules |
| Ansible Automation Platform 2.6 | Containerized (all-in-one or growth) — Automation Controller, Event-Driven Ansible |
| Report server | AWS EC2 t3.micro (eu-west-2), nginx HTTPS, SSH on port 2222 |
| NetBox MCP server | AWS EC2 t3.micro (eu-west-2), netboxlabs/netbox-mcp-server, SSH stdio |
| AAP MCP server | Ansible Automation Platform MCP server — queries jobs, workflows, inventories |

## Trigger Mechanism

NetBox 4.x uses **event rules** to trigger webhooks. The event rule watches for any circuit update and fires a webhook to Event-Driven Ansible:

```
NetBox circuit update
  -> Event rule fires
  -> Webhook POST to EDA event stream
  -> EDA rulebook evaluates: object_type == "circuits.circuit" AND status in ["offline", "failed"]
  -> EDA launches Circuit Failover Workflow on Automation Controller
  -> Workflow passes failed_circuit CID as extra var
```

The playbook then checks the circuit's actual status in NetBox and exits if it's not offline — handling any spurious triggers safely (e.g., a description change on an active circuit).

## Resetting Between Runs

```bash
./reset.sh
```

This runs `pb_reset_demo.yml`, which restores IPLC-GB-AT-PRI to `active` and IPLC-GB-AT-SEC to `offline`. Visual Explorer will return to the starting state with all circuits shown.
