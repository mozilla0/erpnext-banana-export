# Banana Export – Frappe/ERPNext Custom App

Exportiert den ERPNext General Ledger in ein Banana-Buchhaltungs-kompatibles CSV-Format.

## Installation (Frappe Cloud)

1. Dieses GitHub-Repo unter deinem Account forken oder direkt verwenden
2. Frappe Cloud Dashboard → Site → Apps → **Install App**
3. GitHub-URL eingeben → installieren
4. Nach Installation: `bench migrate` wird automatisch ausgeführt

## Installation (self-hosted via bench)

```bash
cd /path/to/frappe-bench
bench get-app https://github.com/jokerit/banana_export
bench --site erp.jokerit.cloud install-app banana_export
bench --site erp.jokerit.cloud migrate
```

## Konfiguration

Nach der Installation:
1. ERPNext → Suchleiste → **Banana Export Settings**
2. Firma, Bankkonten und Kontenmapping prüfen/anpassen
3. Speichern – kein Redeployment nötig

## Verwendung

1. ERPNext → Suchleiste → **Banana Export**
2. Von/Bis-Datum wählen
3. **Vorschau laden** → Buchungszeilen prüfen
4. **CSV Exportieren** → Datei herunterladen
5. CSV in Banana Buchhaltung importieren

## Dateiname-Schema

`erpnext_jan_mär_2025.csv`

## Unterstützte Buchungstypen

| ERPNext Voucher Type    | Banana Bezeichnung   | Stapel  |
|-------------------------|----------------------|---------|
| Sales Invoice           | Kundenrechnung       | #6, #7  |
| Purchase Invoice        | Lieferantenrechnung  | #4, #5  |
| Payment Entry (Receive) | Zahlungseingang      | #8      |
| Payment Entry (Pay)     | Zahlungsausgang      | #9      |
| Journal Entry           | Buchungssatz         | #10     |
| Splitbuchung Debit      | –                    | #1      |
| Splitbuchung Credit     | –                    | #2, #3  |

## MwSt.-Codes

| Rate   | Code | Präfix Aufwand | Präfix Ertrag |
|--------|------|----------------|---------------|
| 8.1%   | 81   | M81            | V81           |
| 2.6%   | 26   | M26            | V26           |
| 0%     | 00   | –              | –             |

## Fremdwährungen

Fremdwährungs-Buchungen werden automatisch erkannt über:
- Bankkonto-Mapping (z.B. Konto 1023 = EUR)
- Invoice-Währung (Purchase/Sales Invoice)

CSV-Zeilen erhalten dann den Suffix `-m` im BookingType (z.B. `#6-m`).

## Changelog

### 1.0.0
- Erstveröffentlichung
- Konfigurationsdialog (Banana Export Settings)
- Vorschau-Tabelle im Browser
- Fremdwährungs-Support (EUR, USD)
