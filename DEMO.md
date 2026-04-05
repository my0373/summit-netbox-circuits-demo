# Summit Demo — Scenario and Architecture

## The Scenario

A global enterprise runs WAN circuits between its UK hub (GB-Bristol) and regional offices including Atlanta (US-Atlanta). The primary circuit goes down. Without automation, the network team would need to:

- Detect the failure and identify the backup circuit manually
- Log into routers at both ends and reconfigure routing
- Update the CMDB to reflect the new topology
- Brief stakeholders with an incident report

With NetBox as the Source of Truth and AAP as the automation engine, the entire process takes seconds and requires no manual intervention beyond telling Copilot what happened.

## The Demo Flow

```
Presenter tells Copilot the circuit has failed
        ↓
NetBox Copilot sets IPLC-GB-AT-PRI → offline
        ↓
NetBox event rule fires → webhook to AAP
        ↓
AAP launches Circuit Failover Workflow
        ↓
  Step 1: Circuit Failover playbook
    - Queries NetBox for the failed circuit and its sites
    - Discovers active backup circuits between the same sites
    - Selects best backup by committed bandwidth
    - Simulates router config push (no real devices in demo)
    - Updates NetBox: primary → offline, backup → active
        ↓
  Step 2: Deploy Report playbook
    - Re-queries NetBox for current circuit state
    - Generates HTML incident report from Jinja2 template
    - Deploys report to the report web server over SSH
        ↓
Visual Explorer map updates live (failed circuit disappears)
        ↓
Presenter opens report URL — shows full incident summary
        ↓
Presenter asks Claude (via NetBox MCP): "What is the status of IPLC-GB-AT-PRI?"
```

## Architecture

```
NetBox Cloud                    AAP / Automation
─────────────────               ──────────────────────────────────────────
┌─────────────┐                 ┌──────────────────────────────────────┐
│   Copilot   │ PATCH circuit   │   Circuit Failover Workflow           │
│   (AI chat) │─── status ──→  │                                      │
└─────────────┘   = offline     │  ┌─────────────────────────────────┐ │
                                │  │ Step 1: Circuit Failover         │ │
┌─────────────┐                 │  │  • Query NetBox for circuit/sites│ │
│   Webhooks  │  POST           │  │  • Find best backup circuit      │ │
│  + Event    │──── launch ──→  │  │  • Simulate router config push  │ │
│   Rules     │  workflow       │  │  • PATCH NetBox: update statuses │ │
└─────────────┘                 │  └────────────────┬────────────────┘ │
                                │                   │ on success        │
┌─────────────┐                 │  ┌────────────────▼────────────────┐ │
│   Visual    │ ← live update   │  │ Step 2: Deploy Report            │ │
│  Explorer   │   (map redraws) │  │  • Re-query NetBox state         │ │
└─────────────┘                 │  │  • Generate HTML report (Jinja2) │ │
                                │  │  • Deploy to report web server   │ │
┌─────────────┐                 │  └─────────────────────────────────┘ │
│  NetBox MCP │ ← status check  └──────────────────────────────────────┘
│   (Claude)  │   at end of demo
└─────────────┘
```

## What the Automation Does

### Step 1 — Circuit Failover (`pb_circuit_failover.yml`)

1. Queries NetBox for the failed circuit CID
2. Guards against spurious triggers: if the circuit is not actually offline or failed, the playbook exits cleanly
3. Resolves the A-side and Z-side sites from circuit terminations
4. Queries all active, `dd`-tagged circuits at both sites
5. Finds circuits present at both ends (excluding the failed one) — these are backup candidates
6. Selects the backup with the highest committed bandwidth
7. Simulates pushing a failover routing config to the routers at both sites
8. PATCHes NetBox: primary circuit → offline, backup circuit → active

### Step 2 — Deploy Report (`pb_deploy_report.yml`)

1. Re-queries NetBox for the current state of the failed circuit and its sites
2. Identifies the now-active backup circuit
3. Queries routers at both sites
4. Renders the HTML failover report from `ansible/templates/failover_report.html.j2`
5. Deploys the report to `/var/www/html/failover_report.html` on the report web server via SSH

### Reset (`pb_reset_demo.yml`)

Fetches all circuits tagged `dd` and PATCHes any non-active ones back to `active`. Safe to run between demo attempts.

## Key Points to Make During the Demo

- **NetBox is the trigger, not a passive CMDB.** One status change in Copilot kicks off the entire automation chain.
- **No hardcoded backup mappings.** The playbook discovers the backup dynamically from NetBox. Add a new circuit in NetBox and it's automatically a candidate next time.
- **Two-step workflow.** The circuit update and report deployment are separate, auditable steps — visible in AAP's job history.
- **NetBox Visual Explorer updates live.** The map reflects the new topology immediately after AAP writes back.
- **The MCP server confirms it.** At the end, Claude can query the NetBox MCP server directly to confirm circuit statuses — no UI required.

## Infrastructure

| Component | Details |
|---|---|
| NetBox Cloud | `ryvr4514.cloud.netboxapp.com` — circuits, devices, Visual Explorer, Copilot, webhooks |
| AAP Controller | `netbox-aap25.demoredhat.com` — workflow, job templates, project, inventory |
| Report server | AWS EC2 t3.micro (eu-west-2), nginx HTTPS, SSH on port 2222 |
| MCP server | AWS EC2 t3.micro (eu-west-2), netboxlabs/netbox-mcp-server, SSH stdio |

## Trigger Mechanism

NetBox 4.x uses **event rules** rather than standalone webhooks. The event rule watches for any circuit update and fires a webhook to the AAP workflow launch endpoint:

```
POST /api/controller/v2/workflow_job_templates/{id}/launch/
Authorization: Bearer <aap_token>
{"extra_vars": {"failed_circuit": "{{ data.cid }}"}}
```

The circuit CID is extracted from the webhook payload via NetBox's Jinja2 `body_template`. The playbook then checks the circuit's actual status in NetBox and exits if it's not offline — handling any spurious triggers safely.

## Resetting Between Runs

```bash
./reset.sh
```

This runs `pb_reset_demo.yml`, which sets all `dd`-tagged circuits back to `active`. Visual Explorer will return to the starting state with all circuits shown.
