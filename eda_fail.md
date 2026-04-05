# EDA Integration — Why We Switched to Direct Webhooks

## What We Were Trying to Do

The original design used Event-Driven Ansible (EDA) as the event routing layer:

```
NetBox webhook → EDA event stream → EDA rulebook activation → AAP job template
```

This is the architecturally "correct" approach for an EDA demo — it showcases how EDA can listen for events, apply rules, and trigger automation without polling.

## What Went Wrong

### The Decision Environment Problem

EDA rulebook activations require a **Decision Environment (DE)** — a container image that has `ansible-rulebook` installed. This is distinct from a standard AAP execution environment (EE), which only needs `ansible` and collections.

We tried every publicly accessible image we could find:

| Image | Result |
|---|---|
| `quay.io/ansible/eda-decision-env:latest` | Pull failed — image does not exist at this path |
| `quay.io/ansible/eda-decision-env:2.4.0` | Pull failed |
| `quay.io/ansible/eda-decision-env:1.0.0` | Pull failed |
| `quay.io/ansible/awx-ee:latest` | Pulled OK, but exited with code 2 — no `ansible-rulebook` binary |
| `quay.io/myork02/netboxee:latest` | Pulled OK, but exited with code 2 — no `ansible-rulebook` binary |
| `registry.redhat.io/ansible-automation-platform-25/de-supported-rhel8:latest` | Pull failed — no registry credentials |
| `registry.redhat.io/ansible-automation-platform-24/de-supported-rhel8:latest` | Pull failed |
| `registry.redhat.io/ansible-automation-platform-25/de-minimal-rhel8:latest` | Pull failed |

The EDA workers on `netbox-aap25.demoredhat.com` can reach `quay.io` (the awx-ee pulled fine), but the official Red Hat DE images are gated behind `registry.redhat.io` which requires subscription credentials not configured on this instance.

The `quay.io/myork02/netboxee` image is a NetBox execution environment built for AAP Controller jobs — it has the right NetBox collections but not `ansible-rulebook`, which is a completely separate binary and Python package used only by EDA.

### The source_mappings API Problem

Even if a working DE image had been available, we hit a second issue: the EDA API's `source_mappings` field (which connects an event stream to a rulebook source) requires a `rulebook_hash` that we couldn't reliably compute from outside the platform. The hash format isn't documented and attempts with SHA256 of the rulebook content were rejected.

### The Webhook Condition Problem

The EDA event stream was receiving events correctly from NetBox. However, the NetBox event rule condition syntax behaved unexpectedly — `postchange.status.value` appeared to evaluate the pre-change value rather than the post-change value in NetBox 4.x, causing the job template to fire on spurious circuit updates.

## What We Switched To

Direct webhook: NetBox event rule → AAP job template `/launch/` endpoint.

```
NetBox event rule → POST /api/controller/v2/job_templates/54/launch/
                         Authorization: Bearer <token>
                         body: {"extra_vars": {"failed_circuit": "{{ data.cid }}"}}
```

NetBox's `body_template` field supports Jinja2, so we can extract the circuit CID directly and format it as AAP expects.

To handle the webhook firing on all circuit updates (not just failures), we added a guard to the playbook:

```yaml
- name: Skip if circuit is not in a failed state
  ansible.builtin.meta: end_play
  when: primary.status.value not in ['offline', 'failed']
```

This means spurious triggers (e.g. a description change on an active circuit) query NetBox, find the circuit is active, and exit cleanly within seconds.

## What Would Fix the EDA Path

If you want to restore the EDA flow in future, you need a Decision Environment image that:

1. Has `ansible-rulebook` installed (`pip install ansible-rulebook`)
2. Has the `ansible.eda` collection
3. Is accessible from the AAP instance (either public quay.io or a local registry)

The simplest fix would be to build a custom DE image:

```dockerfile
FROM registry.redhat.io/ansible-automation-platform-25/de-minimal-rhel8:latest
RUN pip install ansible-rulebook
```

Push it to `quay.io/myork02/netbox-de:latest` (public, no auth required) and update the DE in AAP EDA to use it. Then recreate the rulebook activation with the event stream attached.

The rulebook itself (`rulebooks/rulebook.yml`) and the EDA project/event stream/credentials in AAP are all still in place and correct — only the DE image is the blocker.
