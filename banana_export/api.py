import frappe
import csv
import io
from datetime import datetime


# ─── Einstellungen aus DocType laden ─────────────────────────────────────────

def _load_settings():
    """Liest alle Konfigurationswerte aus Banana Export Settings."""
    settings = frappe.get_single("Banana Export Settings")

    company      = settings.company or "Joker IT AG"
    skip_raw     = settings.skip_accounts or "6944, 2201, 2200"
    skip_accounts = {int(x.strip()) for x in skip_raw.split(",") if x.strip().isdigit()}

    bank_account_currencies = {}
    for row in (settings.bank_account_currencies or []):
        bank_account_currencies[int(row.account_nr)] = row.currency

    account_mapping = {}
    for row in (settings.account_mappings or []):
        account_mapping.setdefault(row.currency, {})[int(row.chf_account)] = int(row.mapped_account)

    return {
        "company":                 company,
        "skip_accounts":           skip_accounts,
        "tax_purchase_account":    2201,
        "tax_sales_account":       2200,
        "bank_account_currencies": bank_account_currencies,
        "account_mapping":         account_mapping,
    }


# ─── Hilfsfunktionen ─────────────────────────────────────────────────────────

def _get_account_number(account_str):
    try:
        return int(account_str.split("-")[0].strip())
    except (ValueError, AttributeError):
        return None


def _get_invoice_currency(voucher_type, voucher_no):
    try:
        doc = frappe.get_doc(voucher_type, voucher_no)
        return doc.currency or "CHF"
    except Exception:
        return "CHF"


def _map_account(account_nr, currency, account_mapping):
    if not account_nr or currency == "CHF" or currency not in account_mapping:
        return account_nr
    return account_mapping[currency].get(account_nr, account_nr)


def _get_tax_code(tax_percent):
    pct = round(tax_percent * 100, 2)
    if 7.3 <= pct <= 8.5:
        return "81", 0.081
    elif 2.3 <= pct <= 2.9:
        return "26", 0.026
    return "00", 0.0


def _get_vat_prefix(debit_account):
    if not debit_account:
        return ""
    if 4000 <= debit_account <= 4999:
        return "M"
    elif 5000 <= debit_account <= 6999:
        return "I"
    elif 1100 <= debit_account <= 1200:
        return "V"
    return ""


def _detect_bank_currency(bookings, bank_account_currencies):
    for b in bookings:
        if b.get("account_nr") in bank_account_currencies:
            return bank_account_currencies[b["account_nr"]]
    return None


def _build_banana_line(booking, btype, debit_account, credit_account,
                        tax_code, no_tax, against, description,
                        stapel, lauf, tax_amount_type,
                        invoice_currency, account_mapping, bank_account_currencies):

    # Währung bestimmen (Priorität: Bankkonto > Invoice > Original)
    detected_currency = None
    if debit_account and debit_account in bank_account_currencies:
        detected_currency = bank_account_currencies[debit_account]
        invoice_currency  = detected_currency
    elif credit_account and credit_account in bank_account_currencies:
        detected_currency = bank_account_currencies[credit_account]
        invoice_currency  = detected_currency

    exchange_currency = (
        detected_currency
        or (invoice_currency if invoice_currency and invoice_currency != "CHF" else None)
        or booking.get("currency", "CHF")
    )

    # Beschreibung
    if description:
        desc = description
    elif against:
        desc = f"#{against} / {booking['payment_id']}"
    else:
        desc = f"#{booking.get('against', '')} / {booking['payment_id']}"

    # Konten + Betrag je nach Typ
    if btype == "debit":
        acc_debit  = _map_account(booking["account_nr"], invoice_currency, account_mapping)
        acc_credit = credit_account
        amount     = booking["debit"]
    else:
        acc_debit  = debit_account
        acc_credit = _map_account(booking["account_nr"], invoice_currency, account_mapping)
        amount     = booking["credit"]

    # VatCode
    vat_code = ""
    vat_amount_type = ""
    if not no_tax and tax_code and tax_code != "00":
        prefix   = _get_vat_prefix(acc_debit)
        vat_code = f"{prefix}{tax_code}"
        vat_amount_type = str(tax_amount_type) if tax_amount_type else ""

    # BookingType: mit "-m" bei Fremdwährung
    foreign_currencies = set(bank_account_currencies.values())
    booking_type = (
        f"{stapel}-m" if invoice_currency in foreign_currencies
        else stapel
    )

    return {
        "TransactionId":    booking["id"],
        "Date":             booking["posting_date"],
        "PaymentType":      booking["payment_type"],
        "Doc":              booking["payment_id"],
        "ExchangeCurrency": exchange_currency,
        "Description":      desc,
        "AccountDebit":     acc_debit,
        "AccountCredit":    acc_credit,
        "AmountCurrency":   amount,
        "Notes":            booking.get("po", ""),
        "VatCode":          vat_code,
        "VatAmountType":    vat_amount_type,
        "Run":              lauf,
        "BookingType":      booking_type,
    }


# ─── Kernlogik ────────────────────────────────────────────────────────────────

def _process(from_date, to_date, cfg):
    """GL-Einträge abrufen und in Banana-Zeilen konvertieren."""

    PAYMENT_TYPE_MAP = {
        "Sales Invoice":    "Kundenrechnung",
        "Purchase Invoice": "Lieferantenrechnung",
        "Journal Entry":    "Buchungssatz",
    }

    gl_entries = frappe.db.get_all(
        "GL Entry",
        filters={
            "company":      cfg["company"],
            "posting_date": ["between", [from_date, to_date]],
            "is_cancelled": 0,
        },
        fields=[
            "name", "posting_date", "account", "debit", "credit",
            "account_currency", "debit_in_account_currency",
            "credit_in_account_currency", "voucher_type", "voucher_no",
            "against", "party", "bill_no", "voucher_subtype",
        ],
        order_by="posting_date asc, voucher_no asc",
    )

    if not gl_entries:
        return [], []

    # Normalisieren
    bookings_raw = []
    for e in gl_entries:
        account_nr = _get_account_number(e.account)
        if account_nr is None:
            continue
        vtype = e.voucher_type or ""
        vsub  = e.voucher_subtype or ""
        if vtype == "Payment Entry":
            pt = ("Zahlungseingang" if vsub == "Receive"
                  else "Zahlungsausgang" if vsub == "Pay"
                  else "Zahlung")
        else:
            pt = PAYMENT_TYPE_MAP.get(vtype, vtype)

        bookings_raw.append({
            "id":           e.name,
            "posting_date": str(e.posting_date),
            "account_nr":   account_nr,
            "payment_id":   e.voucher_no,
            "payment_type": pt,
            "voucher_type": vtype,
            "debit":        float(e.debit  or 0),
            "credit":       float(e.credit or 0),
            "currency":     e.account_currency or "CHF",
            "po":           e.bill_no or "",
            "against":      e.against or "",
        })

    # Nach voucher_no gruppieren
    groups = {}
    for b in bookings_raw:
        groups.setdefault(b["payment_id"], []).append(b)

    lauf         = datetime.now().strftime("%Y%m%d-%H%M%S")
    banana_lines = []
    errors       = []

    tax_pur_acc = cfg["tax_purchase_account"]
    tax_sal_acc = cfg["tax_sales_account"]
    skip        = cfg["skip_accounts"]
    bank_cur    = cfg["bank_account_currencies"]
    acc_map     = cfg["account_mapping"]

    for payment_id, group in groups.items():

        booking         = [b for b in group if b["account_nr"] not in skip]
        tax_purchase    = [b for b in group if b["account_nr"] == tax_pur_acc]
        tax_sales       = [b for b in group if b["account_nr"] == tax_sal_acc]
        debit_bookings  = [b for b in booking if b["debit"]  > 0]
        credit_bookings = [b for b in booking if b["credit"] > 0]

        if not debit_bookings and not credit_bookings:
            continue

        # Währung ermitteln
        invoice_currency = _detect_bank_currency(booking, bank_cur) or "CHF"
        if invoice_currency == "CHF" and booking and booking[0]["voucher_type"] in (
            "Purchase Invoice", "Sales Invoice"
        ):
            invoice_currency = _get_invoice_currency(
                booking[0]["voucher_type"], booking[0]["payment_id"]
            )

        # Steuerprozent
        tax_percent = 0.0
        against     = ""
        if tax_sales:
            total = sum(b["debit"]  for b in debit_bookings)
            tax_s = sum(b["credit"] for b in tax_sales)
            tax_percent = tax_s / (total - tax_s) if (total - tax_s) else 0
            against = credit_bookings[0]["against"] if credit_bookings else ""
        if tax_purchase:
            total = sum(b["credit"] for b in credit_bookings)
            tax_p = sum(b["debit"]  for b in tax_purchase)
            tax_percent = tax_p / (total - tax_p) if (total - tax_p) else 0
            against = debit_bookings[0]["against"] if debit_bookings else ""

        no_tax = (not tax_purchase and not tax_sales) or tax_percent == 0
        if no_tax:
            against = debit_bookings[0]["against"] if debit_bookings else ""

        tax_code, _ = _get_tax_code(tax_percent)

        c_acc = credit_bookings[0]["account_nr"] if credit_bookings else None
        d_acc = debit_bookings[0]["account_nr"]  if debit_bookings  else None

        def make(bobj, btype, dacc, cacc, tc=tax_code, nt=no_tax,
                 ag=against, desc="", stapel="", tamt=None):
            da = _map_account(dacc, invoice_currency, acc_map) if dacc else dacc
            ca = _map_account(cacc, invoice_currency, acc_map) if cacc else cacc
            return _build_banana_line(
                bobj, btype, da, ca, tc, nt, ag, desc,
                stapel, lauf, tamt, invoice_currency, acc_map, bank_cur
            )

        try:
            if len(debit_bookings) > 1:
                # Splitbuchung Debit
                for db in debit_bookings:
                    banana_lines.append(make(db, "debit", None, c_acc, stapel="#1"))

            elif len(credit_bookings) > 1:
                # Splitbuchung Credit
                for cb in credit_bookings:
                    if no_tax:
                        banana_lines.append(make(cb, "credit", d_acc, None,
                                                  nt=True, ag=against, stapel="#2"))
                    else:
                        banana_lines.append(make(cb, "credit", d_acc, None,
                                                  tc=f"{tax_code}-1", stapel="#3", tamt=1))

            elif credit_bookings and tax_purchase:
                # Standard Lieferantenrechnung mit Steuer
                banana_lines.append(make(
                    credit_bookings[0], "credit", d_acc, None,
                    ag=debit_bookings[0]["against"] if debit_bookings else "",
                    stapel="#4",
                ))

            elif credit_bookings and credit_bookings[0]["payment_type"] == "Lieferantenrechnung":
                # Lieferantenrechnung steuerfrei
                banana_lines.append(make(
                    credit_bookings[0], "credit", d_acc, None,
                    ag=debit_bookings[0]["against"] if debit_bookings else "",
                    stapel="#5",
                ))

            elif credit_bookings and tax_sales:
                # Standard Kundenrechnung mit Steuer
                banana_lines.append(make(
                    debit_bookings[0], "debit", None, c_acc,
                    ag=credit_bookings[0]["against"],
                    stapel="#6",
                ))

            elif debit_bookings and debit_bookings[0]["payment_type"] == "Kundenrechnung":
                # Kundenrechnung steuerfrei
                banana_lines.append(make(
                    debit_bookings[0], "debit", None, c_acc,
                    ag=credit_bookings[0]["against"] if credit_bookings else "",
                    stapel="#7",
                ))

            elif debit_bookings and debit_bookings[0]["payment_type"] == "Zahlungseingang":
                # Zahlungseingang
                banana_lines.append(make(
                    debit_bookings[0], "debit", None, c_acc,
                    ag=debit_bookings[0]["against"],
                    stapel="#8",
                ))

            elif credit_bookings and credit_bookings[0]["payment_type"] == "Zahlungsausgang":
                # Zahlungsausgang
                banana_lines.append(make(
                    debit_bookings[0], "debit", None, c_acc,
                    ag=credit_bookings[0]["against"] if credit_bookings else "",
                    stapel="#9",
                ))

            elif credit_bookings and credit_bookings[0]["payment_type"] == "Buchungssatz":
                # Journal Entry: Beschreibung aus cheque_no + remark
                try:
                    je   = frappe.get_doc("Journal Entry", payment_id)
                    desc = f"{je.cheque_no or ''} / {je.remark or ''}"
                except Exception:
                    desc = payment_id
                banana_lines.append(make(
                    debit_bookings[0], "debit", None, c_acc,
                    nt=True,
                    ag=credit_bookings[0]["against"] if credit_bookings else "",
                    desc=desc,
                    stapel="#10",
                ))

            else:
                msg = f"Keine Verarbeitungsmethode für PaymentId {payment_id}"
                errors.append(msg)
                frappe.log_error(msg, "Banana Export")

        except Exception as ex:
            errors.append(f"{payment_id}: {str(ex)}")
            frappe.log_error(frappe.get_traceback(), "Banana Export")

    return banana_lines, errors


# ─── Haupt-API-Methode ────────────────────────────────────────────────────────

@frappe.whitelist()
def generate_banana_csv(from_date, to_date):
    """
    Liest den General Ledger aus und gibt CSV + Vorschau-Daten zurück.
    Wird von der Banana Export Page aufgerufen.
    """
    try:
        cfg   = _load_settings()
        lines, errors = _process(from_date, to_date, cfg)

        if not lines:
            return {"error": "Keine Buchungszeilen generiert.", "skipped": errors}

        # CSV erstellen
        fieldnames = [
            "TransactionId", "Date", "PaymentType", "Doc",
            "ExchangeCurrency", "Description",
            "AccountDebit", "AccountCredit", "AmountCurrency",
            "Notes", "VatCode", "VatAmountType", "Run", "BookingType",
        ]
        output = io.StringIO()
        writer = csv.DictWriter(
            output, fieldnames=fieldnames,
            delimiter=";", extrasaction="ignore", lineterminator="\r\n",
        )
        writer.writeheader()
        writer.writerows(lines)

        # Dateiname: erpnext_jan_mär_2025.csv
        locale_de = {
            1:"jan", 2:"feb", 3:"mär", 4:"apr", 5:"mai",  6:"jun",
            7:"jul", 8:"aug", 9:"sep", 10:"okt", 11:"nov", 12:"dez",
        }
        d_from   = datetime.strptime(from_date, "%Y-%m-%d")
        d_to     = datetime.strptime(to_date,   "%Y-%m-%d")
        filename = (
            f"erpnext_{locale_de[d_from.month]}_"
            f"{locale_de[d_to.month]}_{d_from.year}.csv"
        )

        return {
            "csv":      output.getvalue(),
            "filename": filename,
            "preview":  lines,
            "skipped":  errors,
            "count":    len(lines),
        }

    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Banana Export Fehler")
        return {"error": str(e)}
