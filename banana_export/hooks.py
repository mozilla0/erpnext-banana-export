from . import __version__ as app_version

app_name        = "banana_export"
app_title       = "Banana Export"
app_publisher   = "Joker IT AG"
app_description = "Banana Buchhaltung CSV Export aus ERPNext"
app_version     = "1.0.0"
app_license     = "MIT"

# ── Abhängigkeiten ────────────────────────────────────────────────────────────
required_apps = ["frappe", "erpnext"]

# ── Nach App-Installation: Standardwerte setzen ───────────────────────────────
after_install = "banana_export.setup.after_install"
