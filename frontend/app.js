// Main Application Client Logic
document.addEventListener("DOMContentLoaded", () => {
  // Determine API base URL (clearing stale frontend origins if saved)
  let savedUrl = localStorage.getItem("DOCU_API_URL");
  if (savedUrl && savedUrl.includes("docuextract-frontend")) {
    localStorage.removeItem("DOCU_API_URL");
    savedUrl = null;
  }
  
  let state = {
    apiBaseUrl: savedUrl || window.APP_CONFIG.API_BASE_URL || "https://docuextract-backend-lmts.onrender.com/api/v1",
    selectedFile: null,
    isProcessing: false,
    currentDocument: null,
    historyList: [],
    activeTab: "inspector"
  };

  // DOM Elements
  const dropzone = document.getElementById("dropzone");
  const fileInput = document.getElementById("file-input");
  const uploadForm = document.getElementById("upload-form");
  const docTypeSelect = document.getElementById("doc-type-select");
  const processBtn = document.getElementById("process-btn");
  const filePreview = document.getElementById("file-preview");
  const previewFilename = document.getElementById("preview-filename");
  const previewFilesize = document.getElementById("preview-filesize");
  const removeFileBtn = document.getElementById("remove-file-btn");
  const progressCard = document.getElementById("progress-card");
  const progressStatusText = document.getElementById("progress-status-text");
  const progressPercentage = document.getElementById("progress-percentage");
  const progressBarFill = document.getElementById("progress-bar-fill");
  
  // Health & Settings
  const backendHealthBadge = document.getElementById("backend-health-badge");
  const backendStatusText = document.getElementById("backend-status-text");
  const swaggerNavLink = document.getElementById("swagger-nav-link");
  const settingsModal = document.getElementById("settings-modal");
  const openSettingsBtn = document.getElementById("open-settings-btn");
  const closeSettingsBtn = document.getElementById("close-settings-btn");
  const apiUrlInput = document.getElementById("api-url-input");
  const saveApiUrlBtn = document.getElementById("save-api-url-btn");
  const resetApiUrlBtn = document.getElementById("reset-api-url-btn");

  // Tabs
  const tabInspectorBtn = document.getElementById("tab-inspector-btn");
  const tabHistoryBtn = document.getElementById("tab-history-btn");
  const tabInspector = document.getElementById("tab-inspector");
  const tabHistory = document.getElementById("tab-history");
  const refreshHistoryBtn = document.getElementById("refresh-history-btn");

  // Results View
  const emptyInspectorState = document.getElementById("empty-inspector-state");
  const activeDocumentView = document.getElementById("active-document-view");
  const viewDocName = document.getElementById("view-doc-name");
  const viewDocType = document.getElementById("view-doc-type");
  const viewDocPages = document.getElementById("view-doc-pages");
  const viewProcTime = document.getElementById("view-proc-time");
  const viewAiModel = document.getElementById("view-ai-model");
  const viewStatusBadge = document.getElementById("view-status-badge");
  const validationChecksContainer = document.getElementById("validation-checks-container");
  const extractedFieldsContainer = document.getElementById("extracted-fields-container");
  const tablesCard = document.getElementById("tables-card");
  const tablesContainer = document.getElementById("tables-container");
  const rawJsonViewer = document.getElementById("raw-json-viewer");
  const copyJsonBtn = document.getElementById("copy-json-btn");

  // Stats Counters
  const statTotalDocs = document.getElementById("stat-total-docs");
  const statPassedDocs = document.getElementById("stat-passed-docs");
  const statFailedDocs = document.getElementById("stat-failed-docs");
  const statNaDocs = document.getElementById("stat-na-docs");
  const historyCount = document.getElementById("history-count");
  const historyTableBody = document.getElementById("history-table-body");

  // Initialize
  updateSwaggerLink();
  checkBackendHealth();
  fetchHistory();
  setInterval(checkBackendHealth, 15000);

  // Health Check
  async function checkBackendHealth() {
    if (state.isProcessing) return; // Don't interrupt while busy processing
    try {
      const res = await fetch(`${state.apiBaseUrl}/health`, { signal: AbortSignal.timeout(15000) });
      if (res.ok) {
        const data = await res.json();
        backendHealthBadge.innerHTML = `<span class="status-dot"></span><span>API Live (v${data.version || '1.0'})</span>`;
      } else {
        backendHealthBadge.innerHTML = `<span class="status-dot offline"></span><span>API Error (${res.status})</span>`;
      }
    } catch (err) {
      if (!state.isProcessing) {
        backendHealthBadge.innerHTML = `<span class="status-dot offline"></span><span>API Offline</span>`;
      }
    }
  }

  function updateSwaggerLink() {
    // Base root URL without /api/v1
    const baseRoot = state.apiBaseUrl.replace(/\/api\/v1\/?$/, "");
    swaggerNavLink.href = `${baseRoot}/docs`;
  }

  // File Upload Interactions
  dropzone.addEventListener("click", () => fileInput.click());
  
  dropzone.addEventListener("dragover", (e) => {
    e.preventDefault();
    dropzone.classList.add("dragover");
  });

  dropzone.addEventListener("dragleave", () => dropzone.classList.remove("dragover"));

  dropzone.addEventListener("drop", (e) => {
    e.preventDefault();
    dropzone.classList.remove("dragover");
    if (e.dataTransfer.files.length > 0) {
      handleFileSelection(e.dataTransfer.files[0]);
    }
  });

  fileInput.addEventListener("change", (e) => {
    if (e.target.files.length > 0) {
      handleFileSelection(e.target.files[0]);
    }
  });

  function handleFileSelection(file) {
    const validExtensions = [".pdf", ".jpg", ".jpeg", ".png"];
    const ext = "." + file.name.split(".").pop().toLowerCase();
    
    if (!validExtensions.includes(ext)) {
      alert(`Unsupported file format: ${ext}. Please upload a PDF, JPG, or PNG document.`);
      return;
    }

    state.selectedFile = file;
    previewFilename.textContent = file.name;
    previewFilesize.textContent = formatBytes(file.size);
    filePreview.classList.add("active");
    processBtn.disabled = false;
  }



  removeFileBtn.addEventListener("click", () => {
    state.selectedFile = null;
    fileInput.value = "";
    filePreview.classList.remove("active");
    processBtn.disabled = true;
  });

  // Processing Submission
  uploadForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    if (!state.selectedFile || state.isProcessing) return;

    state.isProcessing = true;
    processBtn.disabled = true;
    progressCard.classList.add("active");
    animateProgress();

    const formData = new FormData();
    formData.append("file", state.selectedFile);
    formData.append("document_type", docTypeSelect.value);

    try {
      const response = await fetch(`${state.apiBaseUrl}/documents/process`, {
        method: "POST",
        body: formData
      });

      const data = await response.json();

      if (!response.ok) {
        const errorDetail = data.detail ? (typeof data.detail === "string" ? data.detail : JSON.stringify(data.detail)) : "Extraction error occurred.";
        throw new Error(errorDetail);
      }

      state.currentDocument = data;
      renderDocumentDetails(data);
      switchTab("inspector");
      fetchHistory();

      progressPercentage.textContent = "100%";
      progressBarFill.style.width = "100%";
      progressStatusText.textContent = "Processing complete!";

      setTimeout(() => {
        progressCard.classList.remove("active");
      }, 1000);

    } catch (err) {
      alert(`Error processing document:\n${err.message}`);
      progressCard.classList.remove("active");
    } finally {
      state.isProcessing = false;
      processBtn.disabled = false;
    }
  });

  function animateProgress() {
    let p = 15;
    progressPercentage.textContent = `${p}%`;
    progressBarFill.style.width = `${p}%`;
    progressStatusText.textContent = "Validating document integrity & page limits...";

    const timer = setInterval(() => {
      if (!state.isProcessing || p >= 85) {
        clearInterval(timer);
        return;
      }
      p += 10;
      progressPercentage.textContent = `${p}%`;
      progressBarFill.style.width = `${p}%`;
      if (p > 40 && p < 70) {
        progressStatusText.textContent = "Running PyMuPDF OCR & AI schema extraction...";
      } else if (p >= 70) {
        progressStatusText.textContent = "Executing deterministic financial validations...";
      }
    }, 400);
  }

  // Render Document Inspector View
  function renderDocumentDetails(doc) {
    emptyInspectorState.style.display = "none";
    activeDocumentView.style.display = "block";

    viewDocName.textContent = doc.document_name;
    viewDocType.textContent = `Type: ${formatDocType(doc.document_type)}`;
    viewDocPages.textContent = `${doc.file_validation.page_count} ${doc.file_validation.page_count === 1 ? 'Page' : 'Pages'}`;
    viewProcTime.textContent = `Duration: ${doc.processing_metadata.processing_duration_ms}ms`;
    viewAiModel.textContent = `Model: ${doc.processing_metadata.ai_model}`;

    // Overall Status Pill
    const overallStatus = doc.validation.overall_status;
    viewStatusBadge.className = `pill pill-${overallStatus === 'PASS' ? 'pass' : overallStatus === 'FAIL' ? 'fail' : 'na'}`;
    viewStatusBadge.textContent = overallStatus === 'PASS' ? 'VALIDATION PASSED' : overallStatus === 'FAIL' ? 'VALIDATION FAILED' : 'NOT APPLICABLE';

    // 1. Validation Checks Grid
    validationChecksContainer.innerHTML = "";
    if (doc.validation.checks && doc.validation.checks.length > 0) {
      doc.validation.checks.forEach(check => {
        const card = document.createElement("div");
        const statusClass = check.status === "PASS" ? "pass" : check.status === "FAIL" ? "fail" : "na";
        card.className = `val-card ${statusClass}`;

        let operandsHtml = "";
        if (check.operands && Object.keys(check.operands).length > 0) {
          operandsHtml = '<div class="val-math-box">';
          for (const [k, v] of Object.entries(check.operands)) {
            operandsHtml += `
              <div>
                <div class="math-item-label">${formatKeyName(k)}</div>
                <div class="math-item-val">${v !== null ? formatValue(v) : '<span style="color: var(--text-dim);">null</span>'}</div>
              </div>
            `;
          }
          if (check.calculated_value !== null) {
            operandsHtml += `
              <div>
                <div class="math-item-label" style="color: var(--accent-cyan);">Calculated Value</div>
                <div class="math-item-val" style="color: var(--accent-cyan);">${formatValue(check.calculated_value)}</div>
              </div>
            `;
          }
          if (check.variance !== null) {
            operandsHtml += `
              <div>
                <div class="math-item-label" style="color: ${check.status === 'PASS' ? 'var(--success)' : 'var(--danger)'};">Variance</div>
                <div class="math-item-val" style="color: ${check.status === 'PASS' ? 'var(--success)' : 'var(--danger)'};">${check.variance}</div>
              </div>
            `;
          }
          operandsHtml += '</div>';
        }

        card.innerHTML = `
          <div class="val-top">
            <div>
              <div class="val-name">${check.formula_name}</div>
              <div class="val-desc">${check.formula_description}</div>
            </div>
            <div class="pill pill-${statusClass}">${check.status}</div>
          </div>
          ${operandsHtml}
          <div class="val-explanation">${check.explanation}</div>
        `;
        validationChecksContainer.appendChild(card);
      });
    } else {
      validationChecksContainer.innerHTML = '<div style="color: var(--text-dim); padding: 1rem;">No validation rules applicable for this document.</div>';
    }

    // 2. Extracted Fields Grid
    extractedFieldsContainer.innerHTML = "";
    const summaryFields = doc.extracted_data.summary_fields || {};
    const fieldEntries = Object.entries(summaryFields);

    if (fieldEntries.length > 0) {
      fieldEntries.forEach(([key, field]) => {
        const card = document.createElement("div");
        card.className = "field-card";

        const val = (field && typeof field === "object") ? field.value : field;
        const confidence = (field && typeof field === "object" && field.confidence) ? Math.round(field.confidence * 100) : null;
        const isMissing = val === null || val === undefined || (field && field.is_missing);
        const sourceText = (field && typeof field === "object" && field.source_text) ? field.source_text : null;
        const pageNum = (field && typeof field === "object" && field.page_number) ? field.page_number : 1;

        card.innerHTML = `
          <div class="field-header">
            <span class="field-name">${formatKeyName(key)}</span>
            ${confidence ? `<span class="pill pill-neutral" style="font-size: 0.7rem; padding: 0.15rem 0.5rem;">${confidence}% conf</span>` : ''}
          </div>
          <div class="field-val ${isMissing ? 'missing' : ''}">${isMissing ? 'null (Not present)' : formatValue(val)}</div>
          ${sourceText ? `<div class="field-evidence">Page ${pageNum}: "${sourceText}"</div>` : ''}
        `;
        extractedFieldsContainer.appendChild(card);
      });
    } else {
      extractedFieldsContainer.innerHTML = '<div style="color: var(--text-dim); padding: 1rem;">No key summary fields extracted.</div>';
    }

    // 3. Tabular Line Items
    const lineItems = doc.extracted_data.line_items || [];
    const tables = doc.extracted_data.tables || {};

    if (lineItems.length > 0 && lineItems[0].values) {
      tablesCard.style.display = "block";
      const detectedPeriods = doc.extracted_data.periods_detected || [];
      const periodCols = detectedPeriods.length > 0 ? detectedPeriods : Object.keys(lineItems[0].values);

      let theadHtml = "<tr><th>#</th><th>Financial Line Item</th>";
      periodCols.forEach(p => { theadHtml += `<th>${p}</th>`; });
      theadHtml += "<th>Source Page</th><th>Confidence</th></tr>";

      let rowsHtml = "";
      lineItems.forEach((item, idx) => {
        rowsHtml += `
          <tr>
            <td>${idx + 1}</td>
            <td><strong>${item.label || item.item_description || 'N/A'}</strong></td>
        `;
        periodCols.forEach(p => {
          const val = item.values ? item.values[p] : null;
          rowsHtml += `<td>${val !== null && val !== undefined ? formatValue(val) : '-'}</td>`;
        });
        rowsHtml += `
            <td>Page ${item.page_number || 1}</td>
            <td><span class="pill pill-neutral" style="font-size: 0.7rem;">${Math.round((item.confidence || 0.98) * 100)}%</span></td>
          </tr>
        `;
      });

      tablesContainer.innerHTML = `
        <div class="table-responsive">
          <table>
            <thead>${theadHtml}</thead>
            <tbody>${rowsHtml}</tbody>
          </table>
        </div>
      `;
    } else if (lineItems.length > 0) {
      tablesCard.style.display = "block";
      let rowsHtml = "";
      lineItems.forEach((item, idx) => {
        rowsHtml += `
          <tr>
            <td>${idx + 1}</td>
            <td><strong>${item.item_description || item.label || 'N/A'}</strong></td>
            <td>${item.quantity !== null ? item.quantity : '-'}</td>
            <td>${item.unit_price !== null ? formatValue(item.unit_price) : '-'}</td>
            <td><strong>${item.line_total !== null ? formatValue(item.line_total) : '-'}</strong></td>
            <td>${item.tax_rate !== null ? (item.tax_rate * 100).toFixed(0) + '%' : '-'}</td>
            <td>Page ${item.page_number || 1}</td>
          </tr>
        `;
      });

      tablesContainer.innerHTML = `
        <div class="table-responsive">
          <table>
            <thead>
              <tr>
                <th>#</th>
                <th>Item Description</th>
                <th>Quantity</th>
                <th>Unit Price</th>
                <th>Line Total</th>
                <th>Tax</th>
                <th>Source Page</th>
              </tr>
            </thead>
            <tbody>${rowsHtml}</tbody>
          </table>
        </div>
      `;
    } else if (tables.balance_sheet_periods || tables.pnl_periods || tables.cash_flow_periods) {
      tablesCard.style.display = "block";
      const periods = tables.balance_sheet_periods || tables.pnl_periods || tables.cash_flow_periods;
      
      let theadHtml = "<tr><th>Metric / Period</th>";
      periods.forEach(p => { theadHtml += `<th>${p.period || 'Period'}</th>`; });
      theadHtml += "</tr>";

      const metricKeys = Object.keys(periods[0] || {}).filter(k => k !== "period");
      let tbodyHtml = "";
      metricKeys.forEach(m => {
        tbodyHtml += `<tr><td><strong>${formatKeyName(m)}</strong></td>`;
        periods.forEach(p => {
          tbodyHtml += `<td>${formatValue(p[m])}</td>`;
        });
        tbodyHtml += "</tr>";
      });

      tablesContainer.innerHTML = `
        <div class="table-responsive">
          <table>
            <thead>${theadHtml}</thead>
            <tbody>${tbodyHtml}</tbody>
          </table>
        </div>
      `;
    } else {
      tablesCard.style.display = "none";
    }


    // 4. Raw JSON Payload
    rawJsonViewer.textContent = JSON.stringify(doc, null, 2);
  }

  // Fetch History & Update Counters
  async function fetchHistory() {
    try {
      const res = await fetch(`${state.apiBaseUrl}/documents`);
      if (!res.ok) return;
      const data = await res.json();
      state.historyList = data.items || [];
      renderHistoryTable(state.historyList);
      updateCounters(state.historyList);
    } catch (err) {
      console.warn("Could not fetch history list:", err);
    }
  }

  function renderHistoryTable(items) {
    historyCount.textContent = items.length;
    if (items.length === 0) {
      historyTableBody.innerHTML = `<tr><td colspan="7" style="text-align: center; color: var(--text-dim); padding: 2rem;">No documents processed yet.</td></tr>`;
      return;
    }

    historyTableBody.innerHTML = items.map(item => `
      <tr>
        <td><strong>#${item.id} ${item.document_name}</strong></td>
        <td><span class="pill pill-neutral">${formatDocType(item.document_type)}</span></td>
        <td>${item.page_count}</td>
        <td>${new Date(item.created_at).toLocaleString()}</td>
        <td><span class="pill pill-${item.validation_status === 'PASS' ? 'pass' : item.validation_status === 'FAIL' ? 'fail' : 'na'}">${item.validation_status}</span></td>
        <td>${item.passed_checks} / ${item.total_checks}</td>
        <td>
          <button class="api-settings-btn inspect-btn" data-id="${item.id}" data-name="${item.document_name}" style="padding: 0.25rem 0.65rem; font-size: 0.78rem;">
            🔍 Inspect
          </button>
        </td>
      </tr>
    `).join("");

    // Attach inspect click listeners strictly by ID
    document.querySelectorAll(".inspect-btn").forEach(btn => {
      btn.addEventListener("click", async () => {
        const docId = btn.getAttribute("data-id");
        console.log(`[DocuExtract] Inspecting document ID: ${docId}`);
        await inspectDocumentById(docId);
      });
    });
  }

  async function inspectDocumentById(docId) {
    try {
      const res = await fetch(`${state.apiBaseUrl}/documents/${encodeURIComponent(docId)}`);
      if (!res.ok) throw new Error("Document not found");
      const doc = await res.json();
      console.log(`[DocuExtract] Loaded Document #${doc.id}: ${doc.document_name} (${doc.document_type})`, doc);
      state.currentDocument = doc;
      renderDocumentDetails(doc);
      switchTab("inspector");
    } catch (err) {
      alert(`Could not load document: ${err.message}`);
    }
  }


  function updateCounters(items) {
    statTotalDocs.textContent = items.length;
    statPassedDocs.textContent = items.filter(i => i.validation_status === "PASS").length;
    statFailedDocs.textContent = items.filter(i => i.validation_status === "FAIL").length;
    statNaDocs.textContent = items.filter(i => i.validation_status === "NOT_APPLICABLE").length;
  }

  // Tabs Switching
  tabInspectorBtn.addEventListener("click", () => switchTab("inspector"));
  tabHistoryBtn.addEventListener("click", () => switchTab("history"));
  refreshHistoryBtn.addEventListener("click", fetchHistory);

  function switchTab(tab) {
    state.activeTab = tab;
    if (tab === "inspector") {
      tabInspectorBtn.classList.add("active");
      tabHistoryBtn.classList.remove("active");
      tabInspector.style.display = "block";
      tabHistory.style.display = "none";
    } else {
      tabHistoryBtn.classList.add("active");
      tabInspectorBtn.classList.remove("active");
      tabHistory.style.display = "block";
      tabInspector.style.display = "none";
      fetchHistory();
    }
  }

  // Copy JSON
  copyJsonBtn.addEventListener("click", () => {
    navigator.clipboard.writeText(rawJsonViewer.textContent).then(() => {
      copyJsonBtn.textContent = "✅ Copied!";
      setTimeout(() => { copyJsonBtn.textContent = "📋 Copy JSON"; }, 2000);
    });
  });

  // Settings Modal
  openSettingsBtn.addEventListener("click", () => {
    apiUrlInput.value = state.apiBaseUrl;
    settingsModal.classList.add("open");
  });

  closeSettingsBtn.addEventListener("click", () => settingsModal.classList.remove("open"));

  saveApiUrlBtn.addEventListener("click", () => {
    let url = apiUrlInput.value.trim().replace(/\/+$/, "");
    if (!url.endsWith("/api/v1")) {
      url += "/api/v1";
    }
    state.apiBaseUrl = url;
    localStorage.setItem("DOCU_API_URL", url);
    settingsModal.classList.remove("open");
    updateSwaggerLink();
    checkBackendHealth();
    fetchHistory();
  });

  resetApiUrlBtn.addEventListener("click", () => {
    localStorage.removeItem("DOCU_API_URL");
    state.apiBaseUrl = window.APP_CONFIG.API_BASE_URL;
    apiUrlInput.value = state.apiBaseUrl;
    updateSwaggerLink();
    checkBackendHealth();
    fetchHistory();
  });

  // Format Helpers
  function formatBytes(bytes) {
    if (bytes === 0) return "0 Bytes";
    const k = 1024;
    const sizes = ["Bytes", "KB", "MB", "GB"];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + " " + sizes[i];
  }

  function formatDocType(type) {
    const map = {
      invoice: "Invoice",
      balance_sheet: "Balance Sheet",
      profit_and_loss: "Profit & Loss",
      cash_flow_statement: "Cash Flow Statement"
    };
    return map[type] || type;
  }

  function formatKeyName(key) {
    return key
      .replace(/_/g, " ")
      .replace(/\b\w/g, l => l.toUpperCase());
  }

  function formatValue(v) {
    if (typeof v === "number") {
      return v.toLocaleString(undefined, { minimumFractionDigits: 0, maximumFractionDigits: 4 });
    }
    return String(v);
  }
});
