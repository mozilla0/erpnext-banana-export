import frappe


def after_install():
    """
    Wird einmalig nach der App-Installation ausgeführt.
    Setzt sinnvolle Standardwerte in Banana Export Settings.
    """
    settings = frappe.get_single("Banana Export Settings")

    # Nur befüllen wenn noch leer (Erstinstallation)
    if settings.company:
        return

    # Firma: erste verfügbare nehmen
    companies = frappe.get_all("Company", pluck="name", limit=1)
    settings.company = companies[0] if companies else "Joker IT AG"

    # Übersprungene Konten
    settings.skip_accounts = "6944, 2201, 2200"

    # Bankkonto → Währung Standardwerte
    settings.append("bank_account_currencies", {"account_nr": 1023, "currency": "EUR"})
    settings.append("bank_account_currencies", {"account_nr": 1025, "currency": "USD"})

    # Kontenmapping EUR
    for chf, mapped, desc in [
        (3200, 3203, "Debitor EUR"),
        (2000, 2003, "Kreditor EUR"),
        (4200, 4205, "Erlöskonto EUR"),
        (1100, 1103, "Gegenkonto Kasse EUR"),
        (1020, 1023, "Bankkonto EUR"),
        (4000, 4003, "Materialeinkauf EUR"),
        (4400, 4403, "Handelswaren EUR"),
    ]:
        settings.append("account_mappings", {
            "currency": "EUR", "chf_account": chf,
            "mapped_account": mapped, "description": desc,
        })

    # Kontenmapping USD
    for chf, mapped, desc in [
        (3200, 3204, "Debitor USD"),
        (2000, 2004, "Kreditor USD"),
        (4200, 4206, "Erlöskonto USD"),
        (1100, 1104, "Gegenkonto Kasse USD"),
        (1020, 1025, "Bankkonto USD"),
        (4000, 4004, "Materialeinkauf USD"),
        (4400, 4404, "Handelswaren USD"),
    ]:
        settings.append("account_mappings", {
            "currency": "USD", "chf_account": chf,
            "mapped_account": mapped, "description": desc,
        })

    settings.save(ignore_permissions=True)
    frappe.db.commit()

    frappe.msgprint(
        "Banana Export: Standardkonfiguration wurde erfolgreich gesetzt.",
        indicator="green",
        alert=True,
    )
