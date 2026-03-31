app_name        = "banana_export"
app_title       = "Banana Export"
app_publisher   = "Joker IT AG"
app_description = "Banana Buchhaltung CSV Export aus ERPNext"
app_version     = "1.0.0"
app_license     = "MIT"
app_email       = "info@jokerit.ch"
app_icon        = "octicon octicon-file-spreadsheet"
app_color       = "#f39c12"

# ── Abhängigkeiten ────────────────────────────────────────────────────────────
required_apps = ["frappe", "erpnext"]

# ── Nach App-Installation: Standardwerte setzen ───────────────────────────────
after_install = "banana_export.banana_export.setup.after_install"
