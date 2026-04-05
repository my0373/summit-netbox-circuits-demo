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
from urllib.parse import urljoin

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

GITHUB_REPO  = "https://github.com/my0373/summit-netbox-circuits-demo"
GITHUB_BRANCH = "main"

ORG_NAME     = "Summit"
ORG_ID       = 5  # confirmed from API

# Controller credential type for NetBox (pre-existing, id=31)
CONTROLLER_NETBOX_CRED_TYPE_ID = 31

# EDA credential type IDs (pre-existing)
EDA_AAP_CRED_TYPE_ID    = 4   # Red Hat Ansible Automation Platform
EDA_TOKEN_STREAM_TYPE_ID = 8  # Token Event Stream

# Decision environment image
DE_IMAGE = "quay.io/ansible/eda-decision-env:latest"

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


# ── Main ───────────────────────────────────────────────────────────────────────

def main():
    ctrl = AAPClient(AAP_HOST, AAP_USER, AAP_PASS)
    eda  = AAPClient(AAP_HOST, AAP_USER, AAP_PASS)

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
    jt_failover, _ = ctrl.get_or_create(
        "/api/controller/v2/job_templates/",
        "Circuit Failover",
        {
            "name": "Circuit Failover",
            "organization": ORG_ID,
            "inventory": inv_id,
            "project": proj_id,
            "playbook": "ansible/pb_circuit_failover.yml",
            "job_type": "run",
            "ask_variables_on_launch": True,
            "extra_vars": "failed_circuit: IPLC-GB-PH-PRI",
            "description": "Automated circuit failover driven by NetBox SoT. Pass failed_circuit as extra var.",
        },
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

    # ── EDA: Decision Environment ──────────────────────────────────────────────
    section("EDA: Decision Environment")
    de, _ = eda.get_or_create(
        "/api/eda/v1/decision-environments/",
        "Summit Demo DE",
        {
            "name": "Summit Demo DE",
            "organization_id": ORG_ID,
            "image_url": DE_IMAGE,
            "description": "Decision environment for Summit NetBox circuit failover demo",
        },
    )
    de_id = de["id"]

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
    if rulebook_id:
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
        print("  SKIPPED — no rulebook found. Re-run after project sync.")
        act_id = None

    # ── Refresh event stream to get URL ───────────────────────────────────────
    section("EDA: Event Stream Webhook URL")
    es_detail = eda.get(f"/api/eda/v1/event-streams/{es_id}/")
    es_webhook_url = es_detail.get("url", "")

    if not es_webhook_url:
        es_webhook_url = f"{AAP_HOST}/api/eda/v1/event-streams/{es_id}/post/"

    print(f"  Webhook URL: {es_webhook_url}")
    print(f"  Token header: Authorization: Token {EVENT_STREAM_TOKEN}")

    # ── NetBox: Webhook ────────────────────────────────────────────────────────
    section("NetBox: Webhook Configuration")

    nb_session = requests.Session()
    nb_session.headers.update({
        "Authorization": f"Token {NETBOX_TOKEN}",
        "Content-Type": "application/json",
    })

    # Check for existing webhook
    existing = nb_session.get(
        f"{NETBOX_URL}/api/extras/webhooks/",
        params={"name": "EDA Circuit Failover"},
    ).json()

    webhook_data = {
        "name": "EDA Circuit Failover",
        "payload_url": es_webhook_url,
        "http_method": "POST",
        "http_content_type": "application/json",
        "additional_headers": f"Authorization: Token {EVENT_STREAM_TOKEN}",
        "body_template": "",
        "enabled": True,
        "type_create": False,
        "type_update": True,
        "type_delete": False,
        "conditions": {
            "and": [
                {
                    "attr": "data.status.value",
                    "value": ["deprovisioning", "failed"],
                    "op": "in"
                }
            ]
        },
        "content_types": ["circuits.circuit"],
    }

    if existing["count"] == 0:
        resp = nb_session.post(f"{NETBOX_URL}/api/extras/webhooks/", json=webhook_data)
        if resp.status_code == 201:
            print(f"  CREATED NetBox webhook: EDA Circuit Failover")
            print(f"  Webhook ID: {resp.json()['id']}")
        else:
            print(f"  ERROR creating webhook: {resp.status_code} — {resp.text[:300]}")
    else:
        wh = existing["results"][0]
        # Update it to ensure it points to the right URL
        resp = nb_session.patch(
            f"{NETBOX_URL}/api/extras/webhooks/{wh['id']}/",
            json={"payload_url": es_webhook_url, "enabled": True},
        )
        print(f"  EXISTS/UPDATED NetBox webhook [{wh['id']}]")

    # ── Summary ────────────────────────────────────────────────────────────────
    section("Setup Complete — Summary")
    print(f"""
  Controller Resources:
    Org:             {ORG_NAME} (id={ORG_ID})
    NetBox Cred:     {netbox_cred['name']} (id={netbox_cred['id']})
    Inventory:       {inventory['name']} (id={inv_id})
    Project:         Summit NetBox Circuits Demo (id={proj_id})
    JT Failover:     Circuit Failover (id={jt_failover_id})
    JT Reset:        Reset Demo (id={jt_reset_id})

  EDA Resources:
    Decision Env:    Summit Demo DE (id={de_id})
    EDA Project:     Summit NetBox Circuits Demo (id={eda_proj_id})
    AAP Cred:        AAP Controller - Summit Demo (id={aap_cred_id})
    Stream Cred:     NetBox Webhook Token (id={stream_cred_id})
    Event Stream:    NetBox Circuit Events (id={es_id})
    Activation:      {"NetBox Circuit Failover (id=" + str(act_id) + ")" if act_id else "NOT CREATED — re-run after project sync"}

  NetBox Webhook:
    URL:    {es_webhook_url}
    Token:  {EVENT_STREAM_TOKEN}
    Trigger: circuit update → status in [deprovisioning, failed]

  Demo flow:
    1. Open Visual Explorer in NetBox — show global WAN map
    2. Use Copilot: "Set IPLC-GB-PH-PRI to deprovisioning — primary link failed"
    3. EDA receives event → triggers Circuit Failover job template
    4. AAP: discovers backup, updates router config (simulated), updates NetBox
    5. Visual Explorer updates — failed circuit gone, backup confirmed active
    6. Reset: run ./reset.sh or launch Reset Demo job template in AAP
""")


def register_report_server(ctrl, inv_id, report_server_ip, report_server_port, private_key_path):
    """Add the report server host to the inventory and create a Machine credential."""

    # ── Machine credential ────────────────────────────────────────────────────
    section("Controller: Machine Credential — Report Server")

    with open(private_key_path) as f:
        private_key = f.read()

    machine_cred, _ = ctrl.get_or_create(
        "/api/controller/v2/credentials/",
        "Summit Demo Report Server SSH",
        {
            "name": "Summit Demo Report Server SSH",
            "organization": ORG_ID,
            "credential_type": 1,  # Machine (SSH)
            "inputs": {
                "username": "ec2-user",
                "ssh_key_data": private_key,
            },
            "description": "SSH key for the Summit demo report web server (EC2)",
        },
    )
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


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Set up AAP for Summit NetBox Circuits Demo")
    parser.add_argument("--report-server-ip", help="Public IP of the report web server")
    parser.add_argument("--report-server-port", type=int, default=2222, help="SSH port of the report server")
    parser.add_argument("--private-key-path", help="Path to the SSH private key for the report server")
    args = parser.parse_args()

    import urllib3
    # Move urllib3 disable here so main() doesn't need it
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

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
