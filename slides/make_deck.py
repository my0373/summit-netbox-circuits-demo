"""
make_deck.py — Generates the Red Hat Summit 2026 demo slide deck.
Run with: uv run --with python-pptx python slides/make_deck.py
"""

from pptx import Presentation
from pptx.util import Inches, Pt, Emu
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN
from pptx.util import Inches, Pt
import os

# ── Theme ──────────────────────────────────────────────────────────────────────
NAVY       = RGBColor(0x0D, 0x1B, 0x2A)
TEAL       = RGBColor(0x00, 0xC2, 0xA8)
WHITE      = RGBColor(0xFF, 0xFF, 0xFF)
GREY       = RGBColor(0xB0, 0xBC, 0xCC)
CARD       = RGBColor(0x14, 0x2A, 0x3E)
RED        = RGBColor(0xEF, 0x44, 0x44)
GREEN      = RGBColor(0x22, 0xC5, 0x5E)

SLIDE_W    = Inches(13.33)
SLIDE_H    = Inches(7.5)

LOGO_PATH  = "/Users/myork/manshed/virtus-slides/netbox_logo_bright.png"
ARCH_PNG   = os.path.join(os.path.dirname(__file__), "architecture.png")
SEQ_PNG    = os.path.join(os.path.dirname(__file__), "sequence.png")

prs = Presentation()
prs.slide_width  = SLIDE_W
prs.slide_height = SLIDE_H

blank = prs.slide_layouts[6]  # completely blank


# ── Helpers ────────────────────────────────────────────────────────────────────

def new_slide():
    s = prs.slides.add_slide(blank)
    bg = s.background.fill
    bg.solid()
    bg.fore_color.rgb = NAVY
    return s


def add_logo(slide, size=Inches(1.4)):
    if os.path.exists(LOGO_PATH):
        slide.shapes.add_picture(
            LOGO_PATH,
            left=SLIDE_W - size - Inches(0.25),
            top=SLIDE_H - size * 0.5 - Inches(0.18),
            width=size,
        )


def txb(slide, text, left, top, width, height,
        size=20, bold=False, color=WHITE, align=PP_ALIGN.LEFT, italic=False):
    box = slide.shapes.add_textbox(left, top, width, height)
    tf  = box.text_frame
    tf.word_wrap = True
    p   = tf.paragraphs[0]
    p.alignment = align
    run = p.add_run()
    run.text = text
    run.font.name   = "Calibri"
    run.font.size   = Pt(size)
    run.font.bold   = bold
    run.font.italic = italic
    run.font.color.rgb = color
    return box


def rect(slide, left, top, width, height, fill=CARD, line=None):
    shape = slide.shapes.add_shape(
        1,  # MSO_SHAPE_TYPE.RECTANGLE
        left, top, width, height
    )
    shape.fill.solid()
    shape.fill.fore_color.rgb = fill
    if line:
        shape.line.color.rgb = line
        shape.line.width = Pt(1.5)
    else:
        shape.line.fill.background()
    return shape


def accent_bar(slide, top=Inches(0.08)):
    """Thin teal bar at the top of the slide."""
    r = slide.shapes.add_shape(1, 0, top, SLIDE_W, Inches(0.06))
    r.fill.solid()
    r.fill.fore_color.rgb = TEAL
    r.line.fill.background()


def bullet_slide(slide, title, bullets, logo=True):
    accent_bar(slide)
    txb(slide, title,
        Inches(0.5), Inches(0.25), Inches(11), Inches(0.75),
        size=32, bold=True, color=TEAL)
    y = Inches(1.2)
    for b in bullets:
        indent = b.startswith("  ")
        text   = b.lstrip()
        col    = GREY if indent else WHITE
        sz     = 18 if indent else 22
        prefix = "    •  " if indent else "•  "
        txb(slide, prefix + text,
            Inches(0.6), y, Inches(11.5), Inches(0.55),
            size=sz, color=col)
        y += Inches(0.58) if not indent else Inches(0.5)
    if logo:
        add_logo(slide)


# ═══════════════════════════════════════════════════════════════════════════════
# Slide 1 — Title
# ═══════════════════════════════════════════════════════════════════════════════
s = new_slide()

# Big teal bar left edge
r = s.shapes.add_shape(1, 0, 0, Inches(0.18), SLIDE_H)
r.fill.solid(); r.fill.fore_color.rgb = TEAL; r.line.fill.background()

txb(s, "Automated Circuit Failover",
    Inches(0.5), Inches(1.6), Inches(9), Inches(1.1),
    size=44, bold=True, color=WHITE)
txb(s, "NetBox Cloud  ·  Event-Driven Ansible  ·  AAP Controller",
    Inches(0.5), Inches(2.75), Inches(9), Inches(0.6),
    size=24, color=TEAL)
txb(s, "Red Hat Summit 2026",
    Inches(0.5), Inches(3.5), Inches(6), Inches(0.5),
    size=20, color=GREY)
txb(s, "Matt York  |  Sales Engineer, NetBox Labs",
    Inches(0.5), Inches(4.1), Inches(6), Inches(0.45),
    size=18, color=GREY, italic=True)

add_logo(s, size=Inches(2.0))


# ═══════════════════════════════════════════════════════════════════════════════
# Slide 2 — The Problem
# ═══════════════════════════════════════════════════════════════════════════════
s = new_slide()
bullet_slide(s, "The Problem: Manual Failover", [
    "Global WAN circuits are business-critical — downtime costs revenue",
    "When a circuit fails, engineers must:",
    "  Open spreadsheets to find the backup circuit and its endpoints",
    "  Manually determine which routers are affected",
    "  SSH into devices and apply config changes",
    "  Update documentation after the fact",
    "Typical manual failover: 45+ minutes",
    "NetBox without automation is still just a better spreadsheet",
])


# ═══════════════════════════════════════════════════════════════════════════════
# Slide 3 — The Solution
# ═══════════════════════════════════════════════════════════════════════════════
s = new_slide()
bullet_slide(s, "The Solution: NetBox as Active Source of Truth", [
    "NetBox Cloud holds every circuit, device, and connection",
    "Copilot AI translates operator intent into precise API actions",
    "A circuit status change fires a webhook — no manual trigger needed",
    "Event-Driven Ansible (EDA) listens and reacts in real time",
    "AAP Controller discovers the backup from NetBox and acts",
    "Visual Explorer map updates live — no stale diagrams",
    "Automated failover: under 30 seconds  ·  Full audit trail",
])


# ═══════════════════════════════════════════════════════════════════════════════
# Slide 4 — Architecture diagram
# ═══════════════════════════════════════════════════════════════════════════════
s = new_slide()
accent_bar(s)
txb(s, "Architecture",
    Inches(0.5), Inches(0.25), Inches(10), Inches(0.7),
    size=32, bold=True, color=TEAL)

if os.path.exists(ARCH_PNG):
    s.shapes.add_picture(ARCH_PNG,
        Inches(0.3), Inches(1.05),
        width=Inches(12.0))

add_logo(s)


# ═══════════════════════════════════════════════════════════════════════════════
# Slide 5 — Demo sequence diagram
# ═══════════════════════════════════════════════════════════════════════════════
s = new_slide()
accent_bar(s)
txb(s, "Demo Sequence",
    Inches(0.5), Inches(0.25), Inches(10), Inches(0.7),
    size=32, bold=True, color=TEAL)

if os.path.exists(SEQ_PNG):
    s.shapes.add_picture(SEQ_PNG,
        Inches(0.5), Inches(1.0),
        width=Inches(11.8))

add_logo(s)


# ═══════════════════════════════════════════════════════════════════════════════
# Slide 6 — Step-by-step demo flow
# ═══════════════════════════════════════════════════════════════════════════════
s = new_slide()
accent_bar(s)
txb(s, "Demo Flow — Step by Step",
    Inches(0.5), Inches(0.25), Inches(11), Inches(0.7),
    size=32, bold=True, color=TEAL)

steps = [
    ("1", "Visual Explorer", "Open the global WAN map — GB-Bristol hub with active circuits to Manila, Tokyo, Bucharest, Managua, Sydney, Atlanta"),
    ("2", "Copilot AI",      'Tell Copilot: "IPLC-GB-PH-PRI has failed — set it to offline"'),
    ("3", "EDA",             "NetBox webhook fires → EDA event stream → rulebook matches → triggers Circuit Failover job"),
    ("4", "AAP Controller",  "Queries NetBox for backup circuit (IPLC-GB-PH-SEC), simulates router config push, updates NetBox"),
    ("5", "Visual Explorer", "Refresh map — failed circuit line is gone, backup confirmed active"),
    ("6", "Report",          "Open the failover report: sites, routers, timeline, ROI comparison"),
    ("7", "Claude + MCP",    "Ask Claude: \"What is the status of IPLC-GB-PH-PRI?\" — live NetBox data confirms the failover"),
]

y = Inches(1.1)
for num, label, desc in steps:
    # Number circle (approximated as small rect)
    nr = s.shapes.add_shape(1, Inches(0.35), y + Inches(0.05), Inches(0.38), Inches(0.38))
    nr.fill.solid(); nr.fill.fore_color.rgb = TEAL; nr.line.fill.background()
    txb(s, num, Inches(0.36), y + Inches(0.02), Inches(0.38), Inches(0.38),
        size=16, bold=True, color=NAVY, align=PP_ALIGN.CENTER)

    txb(s, label, Inches(0.85), y, Inches(2.2), Inches(0.45),
        size=16, bold=True, color=TEAL)
    txb(s, desc,  Inches(3.1), y, Inches(9.8), Inches(0.45),
        size=15, color=WHITE)
    y += Inches(0.52)

add_logo(s)


# ═══════════════════════════════════════════════════════════════════════════════
# Slide 7 — Component deep-dive
# ═══════════════════════════════════════════════════════════════════════════════
s = new_slide()
accent_bar(s)
txb(s, "Key Components",
    Inches(0.5), Inches(0.25), Inches(11), Inches(0.7),
    size=32, bold=True, color=TEAL)

components = [
    ("NetBox Cloud",          TEAL,  "Source of Truth for every circuit, device, and connection.\nCopilot AI + Visual Explorer + Webhook engine."),
    ("Event-Driven Ansible",  RGBColor(0xEE, 0x00, 0x00),  "Listens for circuit status changes via HTTP event stream.\nRulebook fires run_job_template instantly — no polling."),
    ("AAP Controller",        RGBColor(0xEE, 0x00, 0x00),  "Runs the failover playbook. Discovers backup dynamically\nfrom NetBox — no hardcoded circuit mappings."),
    ("Report Server (AWS)",   GREY,  "EC2 t3.micro with nginx + self-signed TLS. AAP uploads\nthe HTML failover report after every run."),
    ("MCP Server (AWS)",      GREY,  "EC2 t3.micro running netbox-mcp-server via SSH stdio.\nAllows Claude Code to query NetBox in natural language."),
]

cols = [(Inches(0.3), Inches(4.8)), (Inches(4.9), Inches(4.5)), (Inches(9.6), Inches(3.55))]
col_idx = 0
row_y   = [Inches(1.1), Inches(3.8)]
row     = 0

for i, (name, col, desc) in enumerate(components):
    if i < 3:
        lx, lw = cols[i][0], cols[i][1]
        ly = row_y[0]
    else:
        lx = cols[i - 3][0] if i == 3 else Inches(5.2)
        lw = cols[0][1] if i == 3 else Inches(7.5)
        ly = row_y[1]

    box = rect(s, lx, ly, lw, Inches(2.3), fill=CARD, line=col)
    txb(s, name, lx + Inches(0.15), ly + Inches(0.15), lw - Inches(0.2), Inches(0.5),
        size=17, bold=True, color=col)
    txb(s, desc, lx + Inches(0.15), ly + Inches(0.65), lw - Inches(0.2), Inches(1.5),
        size=14, color=GREY)

add_logo(s)


# ═══════════════════════════════════════════════════════════════════════════════
# Slide 8 — What the playbook does (no hardcoding)
# ═══════════════════════════════════════════════════════════════════════════════
s = new_slide()
bullet_slide(s, "The Playbook: Driven Entirely by NetBox Data", [
    "Input: just the failed circuit CID (e.g. IPLC-GB-PH-PRI)",
    "Discovers A-side and Z-side sites from circuit terminations in NetBox",
    "Finds all active circuits between those two sites",
    "Selects the best backup by highest committed bandwidth",
    "No hardcoded backup mappings — add a new circuit to NetBox and it is automatically considered",
    "Simulates router config push (stub tasks — real devices optional)",
    "Writes back to NetBox: primary → offline, backup confirmed active",
    "Generates and publishes the HTML failover report",
])


# ═══════════════════════════════════════════════════════════════════════════════
# Slide 9 — Infrastructure overview
# ═══════════════════════════════════════════════════════════════════════════════
s = new_slide()
bullet_slide(s, "Infrastructure", [
    "All infrastructure provisioned with Terraform (infra/)",
    "  Two EC2 t3.micro instances in eu-west-2 (London)",
    "  Single SSH key pair generated by Terraform — never stored in Git",
    "  All resources tagged: Name=RedhatSummitEDADemo, owner=myork@netboxlabs.com",
    "Report server: nginx + self-signed TLS, SSH on port 2222",
    "MCP server: netbox-mcp-server installed via uv, SSH stdio transport",
    "AAP wired up by setup_aap.py — idempotent, re-runnable",
    "NetBox webhook configured automatically — points to EDA event stream",
    "Teardown: cd infra && terraform destroy",
])


# ═══════════════════════════════════════════════════════════════════════════════
# Slide 10 — ROI / Key messages
# ═══════════════════════════════════════════════════════════════════════════════
s = new_slide()
accent_bar(s)
txb(s, "Key Messages",
    Inches(0.5), Inches(0.25), Inches(11), Inches(0.7),
    size=32, bold=True, color=TEAL)

# Two metric boxes
for lx, label, val, col in [
    (Inches(0.5),  "Manual failover", "~45 min", RED),
    (Inches(6.8),  "Automated failover", "< 30 sec", GREEN),
]:
    rect(s, lx, Inches(1.1), Inches(5.9), Inches(2.2), fill=CARD, line=col)
    txb(s, val,   lx + Inches(0.2), Inches(1.25), Inches(5.5), Inches(1.1),
        size=52, bold=True, color=col, align=PP_ALIGN.CENTER)
    txb(s, label, lx + Inches(0.2), Inches(2.1), Inches(5.5), Inches(0.5),
        size=18, color=GREY, align=PP_ALIGN.CENTER)

messages = [
    "NetBox is not just a CMDB — it is an active source of truth that drives automation",
    "EDA eliminates polling: the moment a circuit changes, the response is already running",
    "The playbook discovers backup paths dynamically — it works for any circuit, any site",
    "Every failover is logged in NetBox, captured in AAP job history, and published as a report",
    "MCP lets Claude query live NetBox data — confirm outcomes in natural language",
]

y = Inches(3.55)
for msg in messages:
    txb(s, "✦  " + msg, Inches(0.5), y, Inches(12.3), Inches(0.48),
        size=18, color=WHITE)
    y += Inches(0.52)

add_logo(s)


# ═══════════════════════════════════════════════════════════════════════════════
# Slide 11 — Reset / re-run
# ═══════════════════════════════════════════════════════════════════════════════
s = new_slide()
bullet_slide(s, "Resetting the Demo", [
    "Run ./reset.sh from the project root",
    "  Queries all circuits tagged 'dd' that are not active",
    "  PATCHes every one back to active in NetBox",
    "  Visual Explorer returns to starting state",
    "Or launch the Reset Demo job template in AAP Controller",
    "Can also run individual circuits: IPLC-GB-JP-PRI, IPLC-GB-RO-PRI, etc.",
    "The demo is fully repeatable — no manual cleanup needed",
])


# ═══════════════════════════════════════════════════════════════════════════════
# Slide 12 — MCP: Confirm with Claude (final demo step)
# ═══════════════════════════════════════════════════════════════════════════════
s = new_slide()
accent_bar(s)
txb(s, "Step 7: Confirm with Claude + NetBox MCP",
    Inches(0.5), Inches(0.25), Inches(12), Inches(0.7),
    size=32, bold=True, color=TEAL)

# Left panel — what it is
rect(s, Inches(0.3), Inches(1.05), Inches(4.5), Inches(5.9), fill=CARD, line=TEAL)
txb(s, "What is the NetBox MCP Server?",
    Inches(0.5), Inches(1.2), Inches(4.1), Inches(0.5),
    size=16, bold=True, color=TEAL)

mcp_bullets = [
    "Runs on a dedicated AWS VM",
    "Connected to your NetBox Cloud instance",
    "Read-only — queries only, no writes",
    "Accessed via SSH stdio transport",
    "Registered once with Claude Code:\nclaude mcp add netbox-mcp ...",
    "Claude calls NetBox API tools\nautomatically behind the scenes",
]
by = Inches(1.8)
for b in mcp_bullets:
    txb(s, "•  " + b, Inches(0.5), by, Inches(4.1), Inches(0.65),
        size=14, color=WHITE)
    by += Inches(0.62)

# Right panel — example queries
rect(s, Inches(5.1), Inches(1.05), Inches(7.9), Inches(5.9), fill=CARD, line=GREY)
txb(s, "Example queries at the end of the demo",
    Inches(5.3), Inches(1.2), Inches(7.5), Inches(0.5),
    size=16, bold=True, color=GREY)

queries = [
    ("What is the current status of IPLC-GB-PH-PRI?",
     "Confirms: Deprovisioning — failed circuit is recorded"),
    ("What is the status of IPLC-GB-PH-SEC?",
     "Confirms: Active — backup is live"),
    ("Show me all active circuits between GB-Bristol and PH-Manila-01.",
     "Lists surviving circuits on that route"),
    ("Which circuits are currently not active?",
     "Full view of any degraded paths across the WAN"),
    ("When was IPLC-GB-PH-PRI last changed, and by whom?",
     "Audit trail: timestamp + username from NetBox change log"),
]

qy = Inches(1.85)
for q, ans in queries:
    # Query bubble
    qbox = rect(s, Inches(5.2), qy, Inches(7.6), Inches(0.42), fill=RGBColor(0x0D, 0x2E, 0x4A), line=TEAL)
    txb(s, "❯  " + q, Inches(5.35), qy + Inches(0.04), Inches(7.3), Inches(0.38),
        size=13, bold=True, color=TEAL)
    qy += Inches(0.46)
    txb(s, "    " + ans, Inches(5.35), qy, Inches(7.3), Inches(0.38),
        size=13, color=GREY, italic=True)
    qy += Inches(0.6)

add_logo(s)


# ── Save ───────────────────────────────────────────────────────────────────────
out = os.path.join(os.path.dirname(__file__), "Summit_Demo_Deck.pptx")
prs.save(out)
print(f"Saved: {out}")
