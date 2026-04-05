# Red Hat Summit 2026 — NetBox Circuits Demo

## Project Overview

This project contains assets for a NetBox demo created for **Red Hat Summit 2026**, along with a longer follow-up demo and an accompanying blog post.

The working directory name (`summit-netbox-circuits-demo`) suggests the focus is on NetBox's **circuits and connectivity management** features.

## Deliverables

1. **Summit demo** — short, punchy demo for the Red Hat Summit audience
2. **Follow-up demo** — longer, deeper-dive version for post-Summit follow-ups
3. **Blog post** — accompanying written content (outlet/length TBD)

## Demo Scenario

**Theme:** Automated circuit failover driven by NetBox as the source of truth.

**Flow:**
1. Start with two circuits in NetBox (primary active, secondary standby)
2. Demonstrate the topology in the **Visual Explorer**
3. Trigger a "failure" by disabling the primary link via **NetBox Copilot**
4. The status change fires a **webhook to AAP**
5. AAP runs a workflow that:
   - Performs checks
   - Updates router configuration
   - Brings the secondary circuit into service
6. Return to Visual Explorer to show the updated state

**Key message:** NetBox isn't just a CMDB -- it's an active source of truth that drives real automation.

## Open Questions

- [ ] What format is the Summit demo? (live walkthrough, recorded video, slide deck, or combination)
- [ ] Who is the target audience at Summit? (network engineers, IT ops, DevOps/platform teams, or a mix)
- [ ] What is the "longer follow-up demo" format and scope?
- [ ] Where will the blog be published? (NetBox Labs blog, Red Hat collab, etc.) What length?
- [ ] Are the routers real devices or simulated? (e.g. Cisco CML, containerlab, or stub playbooks)
- [ ] What does "update router information" involve? (BGP failover, static route swap, interface state change, etc.)
- [ ] What circuit types/providers are we modelling? (MPLS, internet, dark fibre, etc.)

## Getting Started

Clone the repo, then set up your Python environment with `uv` and create your local credentials file:

```bash
uv sync          # creates .venv and installs dependencies
./setup.sh       # copies .env.example to .env
```

Add new Python dependencies with:

```bash
uv add <package>
```

Never use `pip install` directly.

This copies `.env.example` to `.env`. Fill in your values:

| Variable | Description |
|---|---|
| `NETBOX_URL` | Your NetBox Cloud instance URL |
| `NETBOX_TOKEN` | NetBox API token (generate under your user profile) |
| `AAP_URL` | Ansible Automation Platform base URL |
| `AAP_USERNAME` | AAP username |
| `AAP_PASSWORD` | AAP password |
| `AAP_TOKEN` | AAP OAuth token (alternative to username/password) |

> `.env` is gitignored and will never be committed. Only `.env.example` is tracked.

## Context

- Created by: Matt York (Sales Engineer, NetBox Labs)
- Event: Red Hat Summit 2026
- Product: NetBox Cloud / NetBox Enterprise (not open-source NetBox)
