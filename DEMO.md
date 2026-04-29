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
NetBox event rule fires → webhook to EDA event stream
        ↓
EDA rulebook triggers Circuit Failover Workflow in AAP
        ↓
  Step 1: Circuit Failover playbook (pb_circuit_failover.yml)
    - Queries NetBox for the failed circuit and its sites
    - Discovers active backup circuits between the same sites
    - Selects best backup by committed bandwidth
    - Pushes real IOS config to gb-brs-rtr-01 (Cisco C8000V EC2)
    - Updates NetBox: primary → offline, backup → active
        ↓
  Step 2: Deploy Report playbook (pb_deploy_report.yml)
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
NetBox Cloud                 EDA + AAP / Automation
─────────────────            ─────────────────────────────────────────────────
┌─────────────┐              ┌───────────────────────────────────────────────┐
│   Copilot   │ PATCH        │                                               │
│   (AI chat) │─── circuit ──┼──→ EDA event stream                           │
└─────────────┘   = offline  │         ↓ rulebook: run_workflow_template      │
                             │   Circuit Failover Workflow                    │
┌─────────────┐  POST to EDA │                                               │
│  Event Rule │──────────────┼──→  ┌─────────────────────────────────────┐   │
│  + Webhook  │  event stream│     │ Step 1: Circuit Failover             │   │
└─────────────┘              │     │  • Query NetBox for circuit/sites    │   │
                             │     │  • Find best backup circuit          │   │
┌─────────────┐              │     │  • Push IOS config to C8000V router  │   │
│   Visual    │ ← live map   │     │  • PATCH NetBox: update statuses     │   │
│  Explorer   │   update     │     └─────────────────┬───────────────────┘   │
└─────────────┘              │                       │ on success             │
                             │     ┌─────────────────▼───────────────────┐   │
┌─────────────┐              │     │ Step 2: Deploy Report                │   │
│  NetBox MCP │ ← status     │     │  • Re-query NetBox state             │   │
│   (Claude)  │   check      │     │  • Generate HTML report (Jinja2)     │   │
└─────────────┘              │     │  • Deploy to report web server       │   │
                             │     └─────────────────────────────────────┘   │
                             └───────────────────────────────────────────────┘
                                              ↓
                                   ┌──────────────────┐
                                   │  Cisco C8000V     │
                                   │  gb-brs-rtr-01    │
                                   │  (EC2 eu-west-2)  │
                                   │  cisco.ios_config │
                                   └──────────────────┘
```

## What the Automation Does

### Step 1 — Circuit Failover (`pb_circuit_failover.yml`)

1. Queries NetBox for the failed circuit CID
2. Guards against spurious triggers: if the circuit is not actually offline or failed, the playbook exits cleanly
3. Resolves the A-side and Z-side sites from circuit terminations
4. Queries all active, `dd`-tagged circuits at both sites
5. Finds circuits present at both ends (excluding the failed one) — these are backup candidates
6. Selects the backup with the highest committed bandwidth
7. Registers `gb-brs-rtr-01` in dynamic inventory using its NetBox primary IP (`18.170.83.110`)
8. Pushes real IOS config via `cisco.ios.ios_config`:
   - Removes: `no ip route 0.0.0.0 0.0.0.0 172.16.0.1`
   - Adds: `ip route 0.0.0.0 0.0.0.0 172.16.1.1`
9. PATCHes NetBox: primary circuit → offline, backup circuit → active

Z-side router (`us-atl-rtr-01`) is logged but not configured — no EC2 instance at Z-side. This is noted in the output with a `[DEMO]` tag.

### Step 2 — Deploy Report (`pb_deploy_report.yml`)

1. Re-queries NetBox for the current state of the failed circuit and its sites
2. Identifies the now-active backup circuit
3. Queries routers at both sites
4. Renders the HTML failover report from `ansible/templates/failover_report.html.j2`
5. Deploys the report to `/var/www/html/failover_report.html` on the report web server via SSH

### Reset (`pb_reset_demo.yml`)

1. Fetches all circuits tagged `dd` and PATCHes any non-active ones back to `active`
2. Sets `IPLC-GB-AT-SEC` to `offline` (the backup that was activated during failover)
3. Registers `gb-brs-rtr-01` in dynamic inventory
4. Restores the primary default route on the router: `ip route 0.0.0.0 0.0.0.0 172.16.0.1`

Safe to run between demo attempts. Visual Explorer returns to the starting state.

## Infrastructure

| Component | Details |
|---|---|
| NetBox Cloud | `app.netboxlabs.com` — circuits, devices, [Visual Explorer](https://app.netboxlabs.com/visual-explorer), Copilot, event rules |
| AAP 2.5 Controller | `netbox-aap25.demoredhat.com` — workflow, job templates, EDA, credentials |
| EDA | `network-netbox-de` DE, `network-netbox-ee-stable` EE (both pre-provisioned on AAP) |
| Report server | AWS EC2 t3.micro (eu-west-2), nginx HTTPS, SSH on port 2222 |
| MCP server | AWS EC2 t3.micro (eu-west-2), netboxlabs/netbox-mcp-server, SSH stdio |
| Cisco router | AWS EC2 c5n.large (eu-west-2), Cisco C8000V IOS-XE 17.15.x — `gb-brs-rtr-01` |

## Trigger Mechanism

NetBox 4.x uses **event rules** rather than standalone webhooks. The event rule watches for any circuit update and fires a webhook to the **EDA event stream** URL:

```
POST https://netbox-aap25.demoredhat.com/eda-event-streams/api/eda/v1/external_event_stream/<id>/post/
Authorization: Bearer <eda_stream_token>
```

EDA's rulebook (`rulebooks/rulebook.yml`) listens on the event stream and calls `run_workflow_template` to launch the `Circuit Failover Workflow` in AAP. The `failed_circuit` extra var is extracted from `{{ event.payload.data.cid }}` in the rulebook.

The playbook then checks the circuit's actual status in NetBox and exits if it's not offline — handling any spurious triggers safely.

## Router Credentials

The Cisco C8000V uses a local IOS user provisioned via cloud-init userdata:

- **Username**: `iosuser`
- **Password**: `iospass`
- **AAP Credential**: `Summit Demo Router` (built-in Network credential type — injects `ANSIBLE_NET_USERNAME` and `ANSIBLE_NET_PASSWORD`)

To SSH in manually for debugging:

```bash
ssh iosuser@18.170.83.110
```

## Resetting Between Runs

```bash
./reset.sh
```

This runs `pb_reset_demo.yml`, which resets all `dd`-tagged circuits in NetBox and restores the primary default route on the Cisco router. Visual Explorer returns to the starting state.
