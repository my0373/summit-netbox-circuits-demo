#!/usr/bin/env python3
"""
setup_aap.py — Configures all AAP Controller and EDA resources for the
Summit NetBox Circuits Demo.

Run with:  uv run --with requests python setup_aap.py

What this creates:
  Controller:
    - NetBox credential (Summit Demo)
    - Localhost inventory + host
    - GitHub project
    - Job template: Circuit Failover
    - Job template: Reset Demo

  EDA:
    - Decision environment
    - EDA project (same GitHub repo)
    - AAP controller credential (for run_job_template)
    - Token event stream credential
    - Event stream (HTTP endpoint NetBox posts to)
    - Rulebook activation

  NetBox:
    - Webhook pointing to the EDA event stream URL
"""

import os
import sys
import time
import json
import base64
import argparse
import requests
from pathlib import Path
from urllib.parse import urljoin

# Auto-load .env from the project root so the script works without pre-sourcing
_env_file = Path(__file__).parent / ".env"
if _env_file.exists():
    with open(_env_file) as _f:
        for _line in _f:
            _line = _line.strip()
            if _line and not _line.startswith("#") and "=" in _line:
                _key, _, _val = _line.partition("=")
                os.environ.setdefault(_key.strip(), _val.strip())

# ── Configuration (all values loaded from environment — see .env) ──────────────

def _require(name):
    val = os.getenv(name)
    if not val:
        print(f"ERROR: environment variable {name} is not set. Source your .env file first.")
        sys.exit(1)
    return val

AAP_HOST    = _require("AAP_URL")
AAP_USER    = _require("AAP_USERNAME")
AAP_PASS    = _require("AAP_PASSWORD")

NETBOX_URL   = _require("NETBOX_URL")
NETBOX_TOKEN = _require("NETBOX_TOKEN")

# AAP_TOKEN is no longer used for the NetBox webhook (EDA event stream is used instead).
# Kept as an optional env var for reference / manual testing.
AAP_TOKEN = os.getenv("AAP_TOKEN", "")

# Router password — set from --router-password CLI arg before main() is called.
# Populated in __main__ block so it can be overridden without touching the env.
ROUTER_PASSWORD = ""

GITHUB_REPO  = "https://github.com/my0373/summit-netbox-circuits-demo"
GITHUB_BRANCH = "main"

ORG_NAME     = "Default"
ORG_ID       = 1  # Default org on new AAP 2.6 instance

# NetBox credential type — created dynamically if not present (see ensure_netbox_cred_type())
CONTROLLER_NETBOX_CRED_TYPE_ID = None  # resolved at runtime

# EDA credential type IDs (pre-existing)
EDA_AAP_CRED_TYPE_ID    = 4   # Red Hat Ansible Automation Platform
EDA_TOKEN_STREAM_TYPE_ID = 8  # Token Event Stream


# Event stream webhook token — set in .env as EDA_STREAM_TOKEN
EVENT_STREAM_TOKEN = _require("EDA_STREAM_TOKEN")

# ── Helpers ────────────────────────────────────────────────────────────────────

class AAPClient:
    def __init__(self, base_url, username, password):
        self.base_url = base_url.rstrip("/")
        self.session = requests.Session()
        self.session.auth = (username, password)
        self.session.verify = False
        self.session.headers.update({"Content-Type": "application/json"})

    def get(self, path, **kwargs):
        url = urljoin(self.base_url + "/", path.lstrip("/"))
        r = self.session.get(url, **kwargs)
        r.raise_for_status()
        return r.json()

    def post(self, path, data):
        url = urljoin(self.base_url + "/", path.lstrip("/"))
        r = self.session.post(url, json=data)
        if r.status_code not in (200, 201, 204):
            print(f"  ERROR {r.status_code}: {r.text[:400]}")
            r.raise_for_status()
        if r.status_code == 204 or not r.text:
            return {}
        return r.json()

    def patch(self, path, data):
        url = urljoin(self.base_url + "/", path.lstrip("/"))
        r = self.session.patch(url, json=data)
        r.raise_for_status()
        return r.json()

    def find(self, path, name):
        """Find a resource by name, return None if not found."""
        result = self.get(path, params={"name": name})
        items = result.get("results", [])
        return items[0] if items else None

    def get_or_create(self, path, name, data, id_field="id"):
        existing = self.find(path, name)
        if existing:
            print(f"  EXISTS  {name} [{existing[id_field]}]")
            return existing, False
        created = self.post(path, data)
        print(f"  CREATED {name} [{created[id_field]}]")
        return created, True


def section(title):
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}")


def wait_for_project_sync(ctrl, project_id, timeout=120):
    """Poll until a controller project sync completes."""
    print(f"  Waiting for project sync (max {timeout}s)...", end="", flush=True)
    deadline = time.time() + timeout
    while time.time() < deadline:
        p = ctrl.get(f"/api/controller/v2/projects/{project_id}/")
        status = p.get("status", "")
        if status == "successful":
            print(" done.")
            return True
        if status in ("failed", "error", "canceled"):
            print(f" FAILED (status={status})")
            return False
        print(".", end="", flush=True)
        time.sleep(5)
    print(" TIMEOUT")
    return False


def wait_for_eda_project_sync(eda, project_id, timeout=120):
    """Poll until an EDA project import completes."""
    print(f"  Waiting for EDA project import (max {timeout}s)...", end="", flush=True)
    deadline = time.time() + timeout
    while time.time() < deadline:
        p = eda.get(f"/api/eda/v1/projects/{project_id}/")
        status = p.get("import_state", "")
        if status == "completed":
            print(" done.")
            return True
        if status in ("failed", "error"):
            print(f" FAILED (status={status})")
            return False
        print(".", end="", flush=True)
        time.sleep(5)
    print(" TIMEOUT")
    return False


def ensure_netbox_cred_type(ctrl):
    """Find or create the custom NetBox credential type that injects NETBOX_URL + NETBOX_TOKEN."""
    all_types = ctrl.get("/api/controller/v2/credential_types/?page_size=100")
    existing = next(
        (ct for ct in all_types.get("results", []) if ct["name"] == "NetBox API"),
        None,
    )
    if existing:
        print(f"  Found credential type: NetBox API (id={existing['id']})")
        return existing["id"]

    print("  Creating credential type: NetBox API")
    created = ctrl.post("/api/controller/v2/credential_types/", {
        "name": "NetBox API",
        "kind": "cloud",
        "description": "NetBox Cloud API credentials — injects NETBOX_URL and NETBOX_TOKEN as env vars",
        "inputs": {
            "fields": [
                {"id": "NETBOX_API", "label": "NetBox URL", "type": "string", "help_text": "Base URL of the NetBox instance"},
                {"id": "NETBOX_TOKEN", "label": "API Token", "type": "string", "secret": True},
            ],
            "required": ["NETBOX_API", "NETBOX_TOKEN"],
        },
        "injectors": {
            "env": {
                "NETBOX_URL": "{{NETBOX_API}}",
                "NETBOX_API": "{{NETBOX_API}}",
                "NETBOX_TOKEN": "{{NETBOX_TOKEN}}",
            }
        },
    })
    print(f"  CREATED credential type: NetBox API (id={created['id']})")
    return created["id"]


# ── Main ───────────────────────────────────────────────────────────────────────

def main():
    global CONTROLLER_NETBOX_CRED_TYPE_ID

    ctrl = AAPClient(AAP_HOST, AAP_USER, AAP_PASS)
    eda  = AAPClient(AAP_HOST, AAP_USER, AAP_PASS)

    # ── Controller: Execution Environment ─────────────────────────────────────
    section("Controller: Execution Environment")
    all_ees = ctrl.get("/api/controller/v2/execution_environments/")
    ee = next((e for e in all_ees.get("results", []) if e["name"] == "network-netbox-ee-stable"), None)
    if not ee:
        # Fall back to default EE on instances that don't have the custom one
        ee = next((e for e in all_ees.get("results", []) if "default" in e["name"].lower()), None)
    ee_id = ee["id"] if ee else None
    if ee_id:
        print(f"  Using EE: {ee['name']} (id={ee_id})")
    else:
        print("  WARNING: no EE found — job templates will use system default.")

    # ── Controller: NetBox credential type ────────────────────────────────────
    section("Controller: NetBox Credential Type")
    CONTROLLER_NETBOX_CRED_TYPE_ID = ensure_netbox_cred_type(ctrl)

    # ── Controller: NetBox credential ──────────────────────────────────────────
    section("Controller: NetBox Credential")
    netbox_cred, _ = ctrl.get_or_create(
        "/api/controller/v2/credentials/",
        "NetBox Cloud - Summit Demo",
        {
            "name": "NetBox Cloud - Summit Demo",
            "organization": ORG_ID,
            "credential_type": CONTROLLER_NETBOX_CRED_TYPE_ID,
            "inputs": {
                "NETBOX_API": NETBOX_URL,
                "NETBOX_TOKEN": NETBOX_TOKEN,
            },
        },
    )

    # ── Controller: Network Device credential ────────────────────────────────
    # Use the built-in "Network" credential type (kind=net) — it injects
    # ANSIBLE_NET_USERNAME and ANSIBLE_NET_PASSWORD automatically.
    # No custom credential type needed (avoids permission issues on shared AAP).
    section("Controller: Network Device Credential")
    all_cred_types = ctrl.get("/api/controller/v2/credential_types/?kind=net")
    net_cred_type = next(
        (ct for ct in all_cred_types.get("results", []) if ct["name"] == "Network"),
        None,
    )
    if net_cred_type is None:
        # Fall back to first net-kind type if "Network" isn't found by exact name
        net_cred_type = all_cred_types["results"][0] if all_cred_types.get("results") else None
    if net_cred_type is None:
        print("  ERROR: no Network credential type found — skipping router credential")
    else:
        print(f"  Using built-in credential type: {net_cred_type['name']} (id={net_cred_type['id']})")

    # Always patch the password — it's regenerated on every infra provisioning run.
    # get_or_create returns the existing object without updating it, so we patch explicitly.
    _net_cred_data = {
        "name": "Summit Demo Router",
        "organization": ORG_ID,
        "credential_type": net_cred_type["id"],
        "inputs": {
            "username": "iosuser",
            "password": ROUTER_PASSWORD,
        },
        "description": "Local IOS user for the Cisco C8000V demo router (gb-brs-rtr-demo)",
    } if net_cred_type else None

    if _net_cred_data:
        existing_net_cred = ctrl.find("/api/controller/v2/credentials/", "Summit Demo Router")
        if existing_net_cred:
            net_cred = ctrl.patch(
                f"/api/controller/v2/credentials/{existing_net_cred['id']}/",
                {"inputs": {"username": "iosuser", "password": ROUTER_PASSWORD}},
            )
            print(f"  UPDATED Summit Demo Router [{net_cred['id']}] — password refreshed")
        else:
            net_cred = ctrl.post("/api/controller/v2/credentials/", _net_cred_data)
            print(f"  CREATED Summit Demo Router [{net_cred['id']}]")
    else:
        net_cred = None

    # ── Controller: Inventory ──────────────────────────────────────────────────
    section("Controller: Inventory")
    inventory, inv_created = ctrl.get_or_create(
        "/api/controller/v2/inventories/",
        "Summit Demo - Localhost",
        {
            "name": "Summit Demo - Localhost",
            "organization": ORG_ID,
            "description": "Localhost inventory for Summit demo playbooks",
        },
    )
    inv_id = inventory["id"]

    # Add localhost host
    existing_hosts = ctrl.get(f"/api/controller/v2/inventories/{inv_id}/hosts/", params={"name": "localhost"})
    if existing_hosts["count"] == 0:
        ctrl.post(f"/api/controller/v2/hosts/", {
            "name": "localhost",
            "inventory": inv_id,
            "variables": "ansible_connection: local\nansible_python_interpreter: '{{ ansible_playbook_python }}'",
        })
        print("  CREATED localhost host")
    else:
        print(f"  EXISTS  localhost host [{existing_hosts['results'][0]['id']}]")

    # ── Controller: Project ────────────────────────────────────────────────────
    section("Controller: Project (GitHub)")
    project, proj_created = ctrl.get_or_create(
        "/api/controller/v2/projects/",
        "Summit NetBox Circuits Demo",
        {
            "name": "Summit NetBox Circuits Demo",
            "organization": ORG_ID,
            "scm_type": "git",
            "scm_url": GITHUB_REPO,
            "scm_branch": GITHUB_BRANCH,
            "scm_update_on_launch": True,
            "description": "Red Hat Summit 2026 — NetBox circuit failover demo",
        },
    )
    proj_id = project["id"]

    # Trigger sync if just created
    if proj_created:
        ctrl.post(f"/api/controller/v2/projects/{proj_id}/update/", {})
        print("  Triggered project sync...")

    if not wait_for_project_sync(ctrl, proj_id):
        print("  WARNING: Project sync did not complete. Job templates may still work if repo is accessible.")

    # ── Controller: Job Template — Circuit Failover ────────────────────────────
    section("Controller: Job Template — Circuit Failover")
    jt_failover_data = {
        "name": "Circuit Failover",
        "organization": ORG_ID,
        "inventory": inv_id,
        "project": proj_id,
        "playbook": "ansible/pb_circuit_failover.yml",
        "job_type": "run",
        "ask_variables_on_launch": True,
        "extra_vars": "failed_circuit: IPLC-GB-AT-PRI",
        "description": "Automated circuit failover driven by NetBox SoT. Pass failed_circuit as extra var.",
    }
    if ee_id:
        jt_failover_data["execution_environment"] = ee_id
    jt_failover, _ = ctrl.get_or_create(
        "/api/controller/v2/job_templates/", "Circuit Failover", jt_failover_data,
    )
    jt_failover_id = jt_failover["id"]

    # Attach NetBox credential to job template
    existing_creds = ctrl.get(f"/api/controller/v2/job_templates/{jt_failover_id}/credentials/")
    cred_ids = [c["id"] for c in existing_creds.get("results", [])]
    if netbox_cred["id"] not in cred_ids:
        ctrl.post(f"/api/controller/v2/job_templates/{jt_failover_id}/credentials/", {
            "id": netbox_cred["id"],
            "associate": True,
        })
        print(f"  Attached NetBox credential to Circuit Failover template")

    # Attach network device credential
    if net_cred and net_cred["id"] not in cred_ids:
        ctrl.post(f"/api/controller/v2/job_templates/{jt_failover_id}/credentials/", {
            "id": net_cred["id"],
            "associate": True,
        })
        print(f"  Attached Router credential to Circuit Failover template")

    # ── Controller: Job Template — Deploy Report ──────────────────────────────
    section("Controller: Job Template — Deploy Report")
    jt_report_data = {
        "name": "Deploy Report",
        "organization": ORG_ID,
        "inventory": inv_id,
        "project": proj_id,
        "playbook": "ansible/pb_deploy_report.yml",
        "job_type": "run",
        "ask_variables_on_launch": True,
        "extra_vars": "failed_circuit: IPLC-GB-AT-PRI",
        "description": "Generates and deploys the HTML failover report to the report web server.",
    }
    if ee_id:
        jt_report_data["execution_environment"] = ee_id
    jt_report, _ = ctrl.get_or_create(
        "/api/controller/v2/job_templates/", "Deploy Report", jt_report_data,
    )
    jt_report_id = jt_report["id"]

    existing_creds = ctrl.get(f"/api/controller/v2/job_templates/{jt_report_id}/credentials/")
    cred_ids = [c["id"] for c in existing_creds.get("results", [])]
    if netbox_cred["id"] not in cred_ids:
        ctrl.post(f"/api/controller/v2/job_templates/{jt_report_id}/credentials/", {
            "id": netbox_cred["id"], "associate": True,
        })
        print(f"  Attached NetBox credential to Deploy Report template")

    # Attach machine credential (SSH to report server) if available
    machine_creds = ctrl.get("/api/controller/v2/credentials/?credential_type__name=Machine")
    machine_cred = next(
        (c for c in machine_creds.get("results", []) if "Report Server" in c["name"]),
        None
    )
    if machine_cred and machine_cred["id"] not in cred_ids:
        ctrl.post(f"/api/controller/v2/job_templates/{jt_report_id}/credentials/", {
            "id": machine_cred["id"], "associate": True,
        })
        print(f"  Attached SSH credential to Deploy Report template")

    # ── Controller: Workflow Template — Circuit Failover Workflow ─────────────
    section("Controller: Workflow Template — Circuit Failover Workflow")
    wf, wf_created = ctrl.get_or_create(
        "/api/controller/v2/workflow_job_templates/",
        "Circuit Failover Workflow",
        {
            "name": "Circuit Failover Workflow",
            "organization": ORG_ID,
            "description": "Automated WAN circuit failover: updates NetBox and deploys the incident report.",
            "ask_variables_on_launch": True,
            "extra_vars": "failed_circuit: IPLC-GB-AT-PRI",
        },
    )
    wf_id = wf["id"]

    if wf_created:
        # Add Node 1: Circuit Failover
        node1 = ctrl.post(
            f"/api/controller/v2/workflow_job_templates/{wf_id}/workflow_nodes/",
            {"unified_job_template": jt_failover_id, "inventory": inv_id},
        )
        node1_id = node1["id"]
        print(f"  Added node 1: Circuit Failover [{node1_id}]")

        # Add Node 2: Deploy Report
        node2 = ctrl.post(
            f"/api/controller/v2/workflow_job_templates/{wf_id}/workflow_nodes/",
            {"unified_job_template": jt_report_id, "inventory": inv_id},
        )
        node2_id = node2["id"]
        print(f"  Added node 2: Deploy Report [{node2_id}]")

        # Link Node 1 → Node 2 on success
        ctrl.post(
            f"/api/controller/v2/workflow_job_template_nodes/{node1_id}/success_nodes/",
            {"id": node2_id},
        )
        print(f"  Linked: Circuit Failover → Deploy Report (on success)")

    # ── Controller: Job Template — Reset Demo ─────────────────────────────────
    section("Controller: Job Template — Reset Demo")
    jt_reset, _ = ctrl.get_or_create(
        "/api/controller/v2/job_templates/",
        "Reset Demo",
        {
            "name": "Reset Demo",
            "organization": ORG_ID,
            "inventory": inv_id,
            "project": proj_id,
            "playbook": "ansible/pb_reset_demo.yml",
            "job_type": "run",
            "description": "Resets all dd-tagged circuits back to active status for demo re-runs.",
            **({"execution_environment": ee_id} if ee_id else {}),
        },
    )
    jt_reset_id = jt_reset["id"]

    existing_creds = ctrl.get(f"/api/controller/v2/job_templates/{jt_reset_id}/credentials/")
    cred_ids = [c["id"] for c in existing_creds.get("results", [])]
    if netbox_cred["id"] not in cred_ids:
        ctrl.post(f"/api/controller/v2/job_templates/{jt_reset_id}/credentials/", {
            "id": netbox_cred["id"],
            "associate": True,
        })
        print(f"  Attached NetBox credential to Reset Demo template")

    # Attach network device credential
    if net_cred and net_cred["id"] not in cred_ids:
        ctrl.post(f"/api/controller/v2/job_templates/{jt_reset_id}/credentials/", {
            "id": net_cred["id"],
            "associate": True,
        })
        print(f"  Attached Router credential to Reset Demo template")

    # ── EDA: Decision Environment ──────────────────────────────────────────────
    section("EDA: Decision Environment")
    # Use the pre-existing network-netbox-de DE (provided by Red Hat, AAP 2.5).
    all_des = eda.get("/api/eda/v1/decision-environments/")
    existing_des = all_des.get("results", [])
    de = next((d for d in existing_des if d["name"] == "network-netbox-de"), None)
    if de is None and existing_des:
        de = existing_des[0]
        print(f"  WARNING: network-netbox-de not found. Falling back to: {de['name']} (id={de['id']})")
        print(f"  Ask your Red Hat counterpart to make network-netbox-de available to the Summit org.")
    elif de is None:
        print("  ERROR: No decision environments found. Cannot create EDA activation.")
    else:
        print(f"  Found DE: {de['name']} (id={de['id']})")
    de_id = de["id"] if de else None

    # ── EDA: Project ───────────────────────────────────────────────────────────
    section("EDA: Project (GitHub)")
    eda_project, eda_proj_created = eda.get_or_create(
        "/api/eda/v1/projects/",
        "Summit NetBox Circuits Demo",
        {
            "name": "Summit NetBox Circuits Demo",
            "url": GITHUB_REPO,
            "description": "Red Hat Summit 2026 — EDA rulebooks for circuit failover",
            "organization_id": ORG_ID,
        },
    )
    eda_proj_id = eda_project["id"]

    if eda_proj_created:
        wait_for_eda_project_sync(eda, eda_proj_id)
    else:
        # Trigger a re-sync
        try:
            eda.post(f"/api/eda/v1/projects/{eda_proj_id}/sync/", {})
            print("  Triggered EDA project re-sync...")
            wait_for_eda_project_sync(eda, eda_proj_id)
        except Exception:
            print("  (sync trigger skipped)")

    # ── EDA: AAP Controller Credential ────────────────────────────────────────
    section("EDA: AAP Controller Credential")
    aap_cred, _ = eda.get_or_create(
        "/api/eda/v1/eda-credentials/",
        "AAP Controller - Summit Demo",
        {
            "name": "AAP Controller - Summit Demo",
            "organization_id": ORG_ID,
            "credential_type_id": EDA_AAP_CRED_TYPE_ID,
            "inputs": {
                "host": AAP_HOST,
                "username": AAP_USER,
                "password": AAP_PASS,
                "verify_ssl": False,
            },
            "description": "AAP controller credentials for EDA run_job_template",
        },
    )
    aap_cred_id = aap_cred["id"]

    # ── EDA: Token Event Stream Credential ────────────────────────────────────
    section("EDA: Token Event Stream Credential")
    stream_cred, _ = eda.get_or_create(
        "/api/eda/v1/eda-credentials/",
        "NetBox Webhook Token",
        {
            "name": "NetBox Webhook Token",
            "organization_id": ORG_ID,
            "credential_type_id": EDA_TOKEN_STREAM_TYPE_ID,
            "inputs": {
                "token": EVENT_STREAM_TOKEN,
            },
            "description": "Shared token for NetBox → EDA webhook authentication",
        },
    )
    stream_cred_id = stream_cred["id"]

    # ── EDA: Event Stream ──────────────────────────────────────────────────────
    section("EDA: Event Stream")
    event_stream, es_created = eda.get_or_create(
        "/api/eda/v1/event-streams/",
        "NetBox Circuit Events",
        {
            "name": "NetBox Circuit Events",
            "organization_id": ORG_ID,
            "eda_credential_id": stream_cred_id,
            "description": "HTTP endpoint that receives NetBox circuit change webhooks",
        },
    )
    es_id = event_stream["id"]
    es_url = event_stream.get("url", "")
    print(f"  Event stream URL: {es_url or '(check EDA UI)'}")

    # ── EDA: Find the rulebook in the synced project ───────────────────────────
    section("EDA: Find Rulebook")
    rulebooks = eda.get("/api/eda/v1/rulebooks/", params={"name": "rulebook.yml", "project_id": eda_proj_id})
    if rulebooks["count"] == 0:
        # Try broader search
        rulebooks = eda.get("/api/eda/v1/rulebooks/", params={"project_id": eda_proj_id})
        print(f"  Available rulebooks in project: {[r['name'] for r in rulebooks['results']]}")

    rulebook = None
    for r in rulebooks["results"]:
        if "rulebook" in r["name"].lower() or r["name"] == "rulebook.yml":
            rulebook = r
            break

    if not rulebook and rulebooks["results"]:
        rulebook = rulebooks["results"][0]

    if rulebook:
        print(f"  Found rulebook: {rulebook['name']} [{rulebook['id']}]")
        rulebook_id = rulebook["id"]
    else:
        print("  WARNING: No rulebook found in EDA project yet. Activation will need manual setup.")
        print("  Try re-running this script after the project sync completes.")
        rulebook_id = None

    # ── EDA: Rulebook Activation ───────────────────────────────────────────────
    section("EDA: Rulebook Activation")
    if rulebook_id and de_id:
        activation_data = {
            "name": "NetBox Circuit Failover",
            "organization_id": ORG_ID,
            "rulebook_id": rulebook_id,
            "decision_environment_id": de_id,
            "event_streams": [{"id": es_id, "source_name": "ansible.eda.webhook"}],
            "eda_credentials": [aap_cred_id],
            "is_enabled": True,
            "restart_policy": "on-failure",
            "description": "Listens for NetBox circuit events and triggers AAP failover workflow",
        }
        activation, act_created = eda.get_or_create(
            "/api/eda/v1/activations/",
            "NetBox Circuit Failover",
            activation_data,
        )
        act_id = activation["id"]

        if not act_created:
            # Ensure it's enabled
            if not activation.get("is_enabled"):
                eda.patch(f"/api/eda/v1/activations/{act_id}/", {"is_enabled": True})
                print("  Re-enabled activation")
    else:
        if not rulebook_id:
            print("  SKIPPED — no rulebook found. Re-run after project sync.")
        if not de_id:
            print("  SKIPPED — no decision environment found.")
        act_id = None

    # ── NetBox: Webhook + Event Rule ──────────────────────────────────────────
    # NetBox 4.x uses Event Rules to trigger webhooks. The webhook object holds
    # the HTTP endpoint config; the event rule determines when it fires.
    #
    # Flow: NetBox circuit update → event rule → webhook → EDA event stream
    #       → EDA rulebook → run_workflow_template → Circuit Failover Workflow
    section("NetBox: Webhook + Event Rule")

    nb_session = requests.Session()
    nb_session.headers.update({
        "Authorization": f"Token {NETBOX_TOKEN}",
        "Content-Type": "application/json",
    })

    if not es_url:
        print("  WARNING: EDA event stream URL not available from API response.")
        print("  Set the webhook payload_url manually in NetBox to the EDA event stream URL.")
        print("  (Find it in AAP EDA → Event Streams → NetBox Circuit Events → URL field)")

    webhook_name = "AAP Circuit Failover"
    webhook_data = {
        "name": webhook_name,
        "payload_url": es_url or "",
        "http_method": "POST",
        "http_content_type": "application/json",
        "additional_headers": f"Authorization: Bearer {EVENT_STREAM_TOKEN}",
        "body_template": "",  # send raw NetBox payload — EDA rulebook reads event.payload.data
        "enabled": True,
        "ssl_verification": False,
    }

    # Create or update the webhook object
    existing_wh = nb_session.get(
        f"{NETBOX_URL}/api/extras/webhooks/",
        params={"name": webhook_name},
    ).json()

    if existing_wh["count"] == 0:
        resp = nb_session.post(f"{NETBOX_URL}/api/extras/webhooks/", json=webhook_data)
        if resp.status_code == 201:
            wh_id = resp.json()["id"]
            print(f"  CREATED webhook: {webhook_name} [{wh_id}]")
            print(f"  Payload URL: {es_url or '(set manually)'}")
        else:
            print(f"  ERROR creating webhook: {resp.status_code} — {resp.text[:300]}")
            wh_id = None
    else:
        wh = existing_wh["results"][0]
        wh_id = wh["id"]
        nb_session.patch(f"{NETBOX_URL}/api/extras/webhooks/{wh_id}/", json={
            "payload_url": es_url or wh.get("payload_url", ""),
            "additional_headers": webhook_data["additional_headers"],
            "body_template": "",
            "enabled": True,
            "ssl_verification": False,
        })
        print(f"  EXISTS/UPDATED webhook [{wh_id}]: {webhook_name}")
        print(f"  Payload URL: {es_url or wh.get('payload_url', '(unchanged)')}")

    # Create or update the event rule that triggers the webhook
    if wh_id:
        event_rule_name = "AAP Circuit Failover"
        existing_er = nb_session.get(
            f"{NETBOX_URL}/api/extras/event-rules/",
            params={"name": event_rule_name},
        ).json()

        er_data = {
            "name": event_rule_name,
            "enabled": True,
            "object_types": ["circuits.circuit"],
            "event_types": ["object_updated"],
            "conditions": None,
            "action_type": "webhook",
            "action_object_type": "extras.webhook",
            "action_object_id": wh_id,
        }

        if existing_er["count"] == 0:
            resp = nb_session.post(f"{NETBOX_URL}/api/extras/event-rules/", json=er_data)
            if resp.status_code == 201:
                print(f"  CREATED event rule: {event_rule_name} [{resp.json()['id']}]")
            else:
                print(f"  ERROR creating event rule: {resp.status_code} — {resp.text[:300]}")
        else:
            er = existing_er["results"][0]
            nb_session.patch(f"{NETBOX_URL}/api/extras/event-rules/{er['id']}/", json={
                "enabled": True,
                "action_object_id": wh_id,
            })
            print(f"  EXISTS/UPDATED event rule [{er['id']}]: {event_rule_name}")

    # ── Summary ────────────────────────────────────────────────────────────────
    section("Setup Complete — Summary")
    print(f"""
  Controller Resources:
    Org:             {ORG_NAME} (id={ORG_ID})
    NetBox Cred:     {netbox_cred['name']} (id={netbox_cred['id']})
    Inventory:       {inventory['name']} (id={inv_id})
    Project:         Summit NetBox Circuits Demo (id={proj_id})
    JT Failover:     Circuit Failover (id={jt_failover_id})
    JT Report:       Deploy Report (id={jt_report_id})
    Workflow:        Circuit Failover Workflow (id={wf_id})
    JT Reset:        Reset Demo (id={jt_reset_id})

  NetBox Integration:
    Webhook:         AAP Circuit Failover → {es_url}
    Event Rule:      AAP Circuit Failover (fires on circuit update)
    Body template:   failed_circuit extracted from {{ data.cid }}
    Note: Playbook guards against spurious triggers — only runs if
          circuit is actually in offline/failed state.

  Demo flow:
    1. Open Visual Explorer in NetBox — show global WAN map
    2. Use Copilot: "Set IPLC-GB-AT-PRI to offline — primary link failed"
    3. NetBox event rule fires → workflow launched in AAP
    4. Step 1 (Circuit Failover): discovers backup, simulates router
       config push, updates NetBox (primary offline, backup active)
    5. Step 2 (Deploy Report): re-queries NetBox, generates HTML report,
       deploys to report web server
    6. Visual Explorer updates — failed circuit gone, backup confirmed active
    7. Open report URL to see full incident summary
    8. Reset: run ./reset.sh or launch Reset Demo job template in AAP
""")


def register_report_server(ctrl, inv_id, report_server_ip, report_server_port, private_key_path):
    """Add the report server host to the inventory and create a Machine credential."""

    # ── Machine credential ────────────────────────────────────────────────────
    section("Controller: Machine Credential — Report Server")

    with open(private_key_path) as f:
        private_key = f.read()

    # Always patch the SSH key — Terraform regenerates it on every infra
    # provisioning run, so the existing credential's key won't match the new
    # report server's authorized_keys without an explicit update.
    _machine_cred_data = {
        "name": "Summit Demo Report Server SSH",
        "organization": ORG_ID,
        "credential_type": 1,  # Machine (SSH)
        "inputs": {
            "username": "ec2-user",
            "ssh_key_data": private_key,
        },
        "description": "SSH key for the Summit demo report web server (EC2)",
    }
    existing_machine_cred = ctrl.find("/api/controller/v2/credentials/", "Summit Demo Report Server SSH")
    if existing_machine_cred:
        machine_cred = ctrl.patch(
            f"/api/controller/v2/credentials/{existing_machine_cred['id']}/",
            {"inputs": {"username": "ec2-user", "ssh_key_data": private_key}},
        )
        print(f"  UPDATED Summit Demo Report Server SSH [{machine_cred['id']}] — key refreshed")
    else:
        machine_cred = ctrl.post("/api/controller/v2/credentials/", _machine_cred_data)
        print(f"  CREATED Summit Demo Report Server SSH [{machine_cred['id']}]")
    machine_cred_id = machine_cred["id"]

    # ── Report server host in inventory ──────────────────────────────────────
    section("Controller: Inventory — Report Server Host")

    existing = ctrl.get(f"/api/controller/v2/inventories/{inv_id}/hosts/",
                        params={"name": report_server_ip})
    if existing["count"] == 0:
        ctrl.post("/api/controller/v2/hosts/", {
            "name": report_server_ip,
            "inventory": inv_id,
            "variables": f"ansible_port: {report_server_port}\nansible_user: ec2-user",
        })
        print(f"  CREATED host {report_server_ip} (port {report_server_port})")
    else:
        host_id = existing["results"][0]["id"]
        ctrl.patch(f"/api/controller/v2/hosts/{host_id}/", {
            "variables": f"ansible_port: {report_server_port}\nansible_user: ec2-user",
        })
        print(f"  UPDATED host {report_server_ip} [{host_id}]")

    # ── Attach machine credential to failover job template ───────────────────
    section("Controller: Attach Machine Credential to Circuit Failover")

    jt_failover = ctrl.find("/api/controller/v2/job_templates/", "Circuit Failover")
    if jt_failover:
        jt_id = jt_failover["id"]
        existing_creds = ctrl.get(f"/api/controller/v2/job_templates/{jt_id}/credentials/")
        cred_ids = [c["id"] for c in existing_creds.get("results", [])]
        if machine_cred_id not in cred_ids:
            ctrl.post(f"/api/controller/v2/job_templates/{jt_id}/credentials/", {
                "id": machine_cred_id,
                "associate": True,
            })
            print("  Attached Machine credential to Circuit Failover template")
        else:
            print("  Machine credential already attached")
    else:
        print("  WARNING: Circuit Failover job template not found")

    section("Report Server Registration Complete")
    print(f"  Host:     {report_server_ip}:{report_server_port}")
    print(f"  Key:      {private_key_path}")
    print(f"  Cred ID:  {machine_cred_id}")


def update_netbox_router_ip(router_ip):
    """Create a /32 IP object in NetBox and set it as gb-brs-rtr-01's primary_ip4.
    Device id=22 is gb-brs-rtr-01 at GB-Bristol — the A-side router for the demo circuit."""
    section("NetBox: Update Router Primary IP")
    nb_session = requests.Session()
    nb_session.headers.update({
        "Authorization": f"Token {NETBOX_TOKEN}",
        "Content-Type": "application/json",
    })
    nb_session.verify = False

    ip_cidr = f"{router_ip}/32"

    # Find or create the IP address object
    existing = nb_session.get(
        f"{NETBOX_URL}/api/ipam/ip-addresses/",
        params={"address": ip_cidr},
    ).json()

    if existing["count"] == 0:
        resp = nb_session.post(f"{NETBOX_URL}/api/ipam/ip-addresses/", json={
            "address": ip_cidr,
            "description": "Cisco demo router EC2 Elastic IP (gb-brs-rtr-demo)",
        })
        if resp.status_code == 201:
            ip_obj = resp.json()
            print(f"  CREATED IP: {ip_cidr} (id={ip_obj['id']})")
        else:
            print(f"  ERROR creating IP: {resp.status_code} — {resp.text[:200]}")
            return
    else:
        ip_obj = existing["results"][0]
        print(f"  EXISTS IP: {ip_cidr} (id={ip_obj['id']})")

    ip_id = ip_obj["id"]

    # Step 1: Assign IP to gb-brs-rtr-01's Gi0/0/1 interface (id=109).
    # NetBox requires an IP to be assigned to a device interface before it can
    # be set as that device's primary_ip4.
    ROUTER_INTERFACE_ID = 109  # Gi0/0/1 on gb-brs-rtr-01 (device id=22)
    resp = nb_session.patch(f"{NETBOX_URL}/api/ipam/ip-addresses/{ip_id}/", json={
        "assigned_object_type": "dcim.interface",
        "assigned_object_id": ROUTER_INTERFACE_ID,
    })
    if resp.status_code == 200:
        print(f"  Assigned {ip_cidr} to interface id={ROUTER_INTERFACE_ID} (Gi0/0/1)")
    else:
        print(f"  ERROR assigning IP to interface: {resp.status_code} — {resp.text[:200]}")
        return

    # Step 2: Set as primary_ip4 on gb-brs-rtr-01 (device id=22)
    resp = nb_session.patch(f"{NETBOX_URL}/api/dcim/devices/22/", json={"primary_ip4": ip_id})
    if resp.status_code == 200:
        print(f"  Updated gb-brs-rtr-01 primary_ip4 → {ip_cidr}")
    else:
        print(f"  ERROR updating device: {resp.status_code} — {resp.text[:200]}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Set up AAP for Summit NetBox Circuits Demo")
    parser.add_argument("--report-server-ip", help="Public IP of the report web server")
    parser.add_argument("--report-server-port", type=int, default=2222, help="SSH port of the report server")
    parser.add_argument("--private-key-path", help="Path to the SSH private key for the report server")
    parser.add_argument("--update-router-ip", help="Public IP of the Cisco router — updates gb-brs-rtr-01 primary IP in NetBox")
    parser.add_argument("--router-password", help="Password for the IOS local user (iosuser) — updates the Summit Demo Router AAP credential")
    args = parser.parse_args()

    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

    # Set global so credential sections in main() pick it up
    if args.router_password:
        import builtins
        globals()["ROUTER_PASSWORD"] = args.router_password

    main()

    if args.report_server_ip and args.private_key_path:
        import urllib3
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        ctrl = AAPClient(AAP_HOST, AAP_USER, AAP_PASS)
        inv = ctrl.find("/api/controller/v2/inventories/", "Summit Demo - Localhost")
        inv_id = inv["id"] if inv else None
        if inv_id:
            register_report_server(ctrl, inv_id, args.report_server_ip,
                                   args.report_server_port, args.private_key_path)
        else:
            print("ERROR: Could not find inventory. Run setup_aap.py without --report-server-ip first.")

        # Patch the Deploy Report job template's extra_vars with the live
        # report server config — these vars come from a gitignored infra.yml
        # locally, so AAP needs them as extra_vars to know where to publish.
        jt = ctrl.find("/api/controller/v2/job_templates/", "Deploy Report")
        if jt:
            extra_vars = (
                "failed_circuit: IPLC-GB-AT-PRI\n"
                f"report_server_host: \"{args.report_server_ip}\"\n"
                f"report_server_port: {args.report_server_port}\n"
                "report_server_user: \"ec2-user\"\n"
                "report_server_path: \"/var/www/html/failover_report.html\"\n"
                f"report_url: \"https://{args.report_server_ip}/failover_report.html\"\n"
            )
            ctrl.patch(f"/api/controller/v2/job_templates/{jt['id']}/",
                       {"extra_vars": extra_vars})
            print(f"  PATCHED Deploy Report extra_vars with report_server_host={args.report_server_ip}")

    if args.update_router_ip:
        update_netbox_router_ip(args.update_router_ip)
