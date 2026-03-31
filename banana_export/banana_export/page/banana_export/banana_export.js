frappe.pages["banana-export"].on_page_load = function (wrapper) {

  const page = frappe.ui.make_app_page({
    parent: wrapper,
    title: "Banana Buchhaltung Export",
    single_column: true,
  });

  // ── Datumsfelder ──────────────────────────────────────────────────────────
  const fromDate = page.add_field({
    fieldtype: "Date",
    fieldname: "from_date",
    label: "Von Datum",
    default: frappe.datetime.year_start(),
  });

  const toDate = page.add_field({
    fieldtype: "Date",
    fieldname: "to_date",
    label: "Bis Datum",
    default: frappe.datetime.get_today(),
  });

  // ── Buttons ───────────────────────────────────────────────────────────────
  page.add_inner_button("Vorschau laden", () => runExport(false));

  page.add_inner_button("CSV Exportieren", () => runExport(true));

  page.add_inner_button("⚙ Einstellungen", () => {
    frappe.set_route("Form", "Banana Export Settings");
  });

  // ── HTML-Gerüst für Vorschau ──────────────────────────────────────────────
  $(wrapper).find(".page-content").append(`
    <div id="bp-wrap" style="padding:16px 20px; display:none;">

      <div id="bp-summary"
           style="margin-bottom:10px; font-size:13px; color:#6c757d;">
      </div>

      <div id="bp-errors" style="margin-bottom:10px;"></div>

      <div style="overflow-x:auto;">
        <table class="table table-bordered table-hover table-sm"
               style="font-size:12px; min-width:900px;">
          <thead style="background:#f5f7fa;">
            <tr>
              <th style="white-space:nowrap;">Datum</th>
              <th>Typ</th>
              <th>Beleg-Nr.</th>
              <th style="min-width:220px;">Beschreibung</th>
              <th style="text-align:right;">Soll</th>
              <th style="text-align:right;">Haben</th>
              <th style="text-align:right;">Betrag</th>
              <th>Währung</th>
              <th>MwSt.</th>
              <th>Stapel</th>
            </tr>
          </thead>
          <tbody id="bp-tbody"></tbody>
        </table>
      </div>

      <div style="margin-top:14px; display:flex;
                  justify-content:space-between; align-items:center;">
        <div id="bp-totals" style="font-size:12px; color:#6c757d;"></div>
        <button class="btn btn-primary btn-sm" id="bp-dl-btn"
                style="display:none;">
          ⬇&nbsp; CSV Herunterladen
        </button>
      </div>

    </div>
  `);

  // ── Zustand ───────────────────────────────────────────────────────────────
  let _lastResult = null;

  // ── Export ausführen ──────────────────────────────────────────────────────
  function runExport(autoDownload) {
    const from = fromDate.get_value();
    const to   = toDate.get_value();

    if (!from || !to) {
      frappe.msgprint("Bitte Von- und Bis-Datum ausfüllen.");
      return;
    }

    frappe.show_progress("Exportiere…", 30, 100, "Buchungen werden verarbeitet…");
    $("#bp-wrap").hide();
    $("#bp-dl-btn").hide();

    frappe.call({
      method: "banana_export.banana_export.api.generate_banana_csv",
      args:   { from_date: from, to_date: to },
      callback(r) {
        frappe.hide_progress();
        const msg = r.message;

        if (!msg || msg.error) {
          frappe.msgprint({
            title: "Fehler",
            message: msg?.error || "Unbekannter Fehler",
            indicator: "red",
          });
          return;
        }

        _lastResult = msg;
        renderPreview(msg, from, to);
        if (autoDownload) triggerDownload(msg);
      },
      error() {
        frappe.hide_progress();
        frappe.msgprint("Serverfehler – Details im ERPNext Error Log.");
      },
    });
  }

  // ── Vorschau rendern ──────────────────────────────────────────────────────
  function renderPreview(msg, from, to) {
    const rows  = msg.preview || [];
    const $tbody = $("#bp-tbody").empty();
    const $sum   = $("#bp-summary");
    const $err   = $("#bp-errors").empty();

    // Zusammenfassung
    $sum.html(
      `<strong>${msg.count}</strong> Buchungszeilen &nbsp;|&nbsp; ` +
      `Zeitraum: <strong>${from}</strong> – <strong>${to}</strong> &nbsp;|&nbsp; ` +
      `Datei: <code>${msg.filename}</code>`
    );

    // Warnungen / übersprungene Einträge
    if (msg.skipped && msg.skipped.length) {
      const html = msg.skipped.map(e =>
        `<div class="alert alert-warning"
              style="padding:3px 10px; margin:2px 0; font-size:11px;">
           ⚠ ${frappe.utils.escape_html(e)}
         </div>`
      ).join("");
      $err.html(html);
    }

    // Summen für Totals
    let totalCHF = 0, countFX = 0;

    rows.forEach(row => {
      const amt     = parseFloat(row.AmountCurrency) || 0;
      const isFX    = row.ExchangeCurrency && row.ExchangeCurrency !== "CHF";
      const hasVat  = row.VatCode && row.VatCode !== "";
      const color   = isFX ? "color:#0055aa;" : "";

      if (isFX) countFX++; else totalCHF += amt;

      $tbody.append(`
        <tr style="${color}">
          <td style="white-space:nowrap;">${row.Date}</td>
          <td>
            <span style="background:#e8f4f8; color:#333;
                         border-radius:3px; padding:1px 5px; font-size:11px;">
              ${frappe.utils.escape_html(row.PaymentType)}
            </span>
          </td>
          <td style="font-size:11px; white-space:nowrap;">
            ${frappe.utils.escape_html(row.Doc)}
          </td>
          <td style="max-width:240px; overflow:hidden;
                     text-overflow:ellipsis; white-space:nowrap;"
              title="${frappe.utils.escape_html(row.Description)}">
            ${frappe.utils.escape_html(row.Description)}
          </td>
          <td style="text-align:right;">${row.AccountDebit  || ""}</td>
          <td style="text-align:right;">${row.AccountCredit || ""}</td>
          <td style="text-align:right; font-weight:500;">
            ${fmtAmt(row.AmountCurrency)}
          </td>
          <td>${frappe.utils.escape_html(row.ExchangeCurrency || "")}</td>
          <td>
            ${hasVat
              ? `<span style="color:#c0392b; font-weight:500;">
                   ${frappe.utils.escape_html(row.VatCode)}
                 </span>`
              : ""}
          </td>
          <td style="color:#999; font-size:10px;">
            ${frappe.utils.escape_html(row.BookingType || "")}
          </td>
        </tr>
      `);
    });

    // Totals
    $("#bp-totals").html(
      `CHF-Zeilen: <strong>${fmtAmt(totalCHF)}</strong> &nbsp;|&nbsp; ` +
      `Fremdwährungs-Zeilen: <strong>${countFX}</strong>`
    );

    $("#bp-wrap").show();
    $("#bp-dl-btn").show();
  }

  // ── Betrag formatieren ────────────────────────────────────────────────────
  function fmtAmt(val) {
    const n = parseFloat(val);
    if (isNaN(n)) return val || "";
    return n.toLocaleString("de-CH", {
      minimumFractionDigits:  2,
      maximumFractionDigits:  2,
    });
  }

  // ── CSV herunterladen ─────────────────────────────────────────────────────
  function triggerDownload(msg) {
    const blob = new Blob(["\uFEFF" + msg.csv], {
      type: "text/csv;charset=utf-8;",
    });
    const url = URL.createObjectURL(blob);
    const a   = document.createElement("a");
    a.href = url;
    a.download = msg.filename;
    a.click();
    URL.revokeObjectURL(url);
    frappe.show_alert({
      message:   `Datei „${msg.filename}" wird heruntergeladen.`,
      indicator: "green",
    });
  }

  // ── Download-Button ───────────────────────────────────────────────────────
  $(document).on("click", "#bp-dl-btn", function () {
    if (_lastResult) triggerDownload(_lastResult);
  });
};
