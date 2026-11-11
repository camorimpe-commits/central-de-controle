// State
let token = localStorage.getItem("optima_token");
let currentUser = null;
let trendChartInstance = null;
let paretoChartInstance = null;
let currentRankingsData = [];

// Currency and number formatters
const formatBRL = (val) => {
  return new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL' }).format(val || 0);
};

const formatNumber = (val) => {
  return new Intl.NumberFormat('pt-BR').format(val || 0);
};

// Check authentication
function checkAuth() {
  if (!token) {
    window.location.href = "/login";
    return false;
  }
  try {
    currentUser = JSON.parse(localStorage.getItem("optima_user") || "{}");
    if (currentUser.name) {
      document.getElementById("userName").textContent = currentUser.name;
      document.getElementById("userRole").textContent = currentUser.role_title || currentUser.role;
      if (currentUser.avatar) {
        document.getElementById("userAvatar").src = currentUser.avatar;
      }
    }
  } catch (e) {
    console.error("Failed to parse user", e);
  }
  return true;
}

function logout() {
  localStorage.removeItem("optima_token");
  localStorage.removeItem("optima_user");
  window.location.href = "/login";
}

// Toast Notifications
function showToast(message, type = "info") {
  const container = document.getElementById("toastContainer");
  const toast = document.createElement("div");
  toast.className = `toast ${type}`;
  
  const icon = type === "success" ? "✅" : (type === "error" ? "❌" : "ℹ️");
  toast.innerHTML = `<span>${icon}</span><span>${message}</span>`;
  container.appendChild(toast);

  setTimeout(() => {
    toast.style.opacity = "0";
    toast.style.transform = "translateX(50px)";
    setTimeout(() => toast.remove(), 300);
  }, 4000);
}

// Initial Setup
document.addEventListener("DOMContentLoaded", async () => {
  if (!checkAuth()) return;
  setupDragAndDrop();
  await loadFilterOptions();
  await refreshDashboard();
  setupAutoRefreshPoll();
});

// Load Dropdown Options
async function loadFilterOptions() {
  try {
    const resp = await fetch("/api/metrics/options", {
      headers: { "Authorization": `Bearer ${token}` }
    });
    if (!resp.ok) return;
    const data = await resp.json();

    const yearSelect = document.getElementById("yearSelect");
    const monthSelect = document.getElementById("monthSelect");
    const temaSelect = document.getElementById("temaSelect");

    // Years
    data.years.forEach(y => {
      const opt = document.createElement("option");
      opt.value = y;
      opt.textContent = `Ano ${y}`;
      yearSelect.appendChild(opt);
    });

    // Months
    const monthNames = {
      jan: "Janeiro", fev: "Fevereiro", mar: "Março", abr: "Abril",
      mai: "Maio", jun: "Junho", jul: "Julho", ago: "Agosto",
      set: "Setembro", out: "Outubro", nov: "Novembro", dez: "Dezembro"
    };
    data.months.forEach(m => {
      const opt = document.createElement("option");
      opt.value = m;
      opt.textContent = monthNames[m] || m.toUpperCase();
      monthSelect.appendChild(opt);
    });

    // Temas
    data.temas.forEach(t => {
      const opt = document.createElement("option");
      opt.value = t;
      opt.textContent = t;
      temaSelect.appendChild(opt);
    });

    document.getElementById("dataStatusText").textContent = `Base: ${formatNumber(data.total_records)} Registros (${data.source})`;
  } catch (err) {
    console.error("Failed to load options", err);
  }
}

// Apply Filters
function applyFilters() {
  refreshDashboard();
}

function resetFilters() {
  document.getElementById("yearSelect").value = "all";
  document.getElementById("monthSelect").value = "all";
  document.getElementById("temaSelect").value = "all";
  refreshDashboard();
}

function getFilterParams() {
  const y = document.getElementById("yearSelect").value;
  const m = document.getElementById("monthSelect").value;
  const t = document.getElementById("temaSelect").value;

  const params = new URLSearchParams();
  if (y && y !== "all") params.append("year", y);
  if (m && m !== "all") params.append("month", m);
  if (t && t !== "all") params.append("tema", t);
  return params.toString();
}

// Refresh Full Dashboard
async function refreshDashboard() {
  const query = getFilterParams();
  await Promise.all([
    fetchSummaryKPIs(query),
    fetchDecisionInsights(query),
    fetchTrendData(query),
    fetchParetoData(query),
    fetchRankings(query),
    fetchDeviations(query)
  ]);
}

// 1. Fetch Executive KPIs
async function fetchSummaryKPIs(query) {
  try {
    const resp = await fetch(`/api/metrics/summary?${query}`, {
      headers: { "Authorization": `Bearer ${token}` }
    });
    if (!resp.ok) return;
    const kpi = await resp.json();

    document.getElementById("kpiEmpenhado").textContent = formatBRL(kpi.total_empenhado);
    document.getElementById("kpiLiquidado").textContent = formatBRL(kpi.total_liquidado);
    document.getElementById("kpiPago").textContent = formatBRL(kpi.total_pago);
    document.getElementById("kpiSLA").textContent = `${kpi.sla_medio_dias} dias`;

    document.getElementById("kpiTaxaLiq").textContent = `${kpi.taxa_liquidacao}%`;
    document.getElementById("kpiLiqProgress").style.width = `${Math.min(100, kpi.taxa_liquidacao)}%`;

    document.getElementById("kpiTaxaExec").textContent = `${kpi.taxa_execucao}%`;
    document.getElementById("kpiExecProgress").style.width = `${Math.min(100, kpi.taxa_execucao)}%`;

    document.getElementById("kpiSLACompliance").textContent = `${kpi.sla_compliance_rate}% no prazo`;
    document.getElementById("kpiTransacoesCount").textContent = `${formatNumber(kpi.total_transacoes)} transações`;

    document.getElementById("kpiIGEO").textContent = `${kpi.igeo_score} / 100`;
    const igeoBadge = document.getElementById("kpiIGEOStatus");
    igeoBadge.textContent = kpi.status_class;
    igeoBadge.className = `status-badge ${kpi.status_color}`;

    document.getElementById("kpiAnomalias").textContent = kpi.anomalias_sla_count;
    document.getElementById("dataStatusText").textContent = `Base: ${formatNumber(kpi.total_transacoes)} Registros | Atualizado às ${kpi.last_updated}`;
  } catch (e) {
    console.error("Error fetching summary KPIs", e);
  }
}

// 2. Fetch Strategic Decision Cards
async function fetchDecisionInsights(query) {
  try {
    const resp = await fetch(`/api/decisions/insights?${query}`, {
      headers: { "Authorization": `Bearer ${token}` }
    });
    if (!resp.ok) return;
    const insights = await resp.json();

    const grid = document.getElementById("decisionCardsGrid");
    grid.innerHTML = "";

    insights.forEach(item => {
      const card = document.createElement("div");
      card.className = "decision-card-item";
      card.innerHTML = `
        <div>
          <div class="decision-card-top">
            <span class="decision-category">${item.categoria}</span>
            <span class="decision-impact">${item.impacto_estimado}</span>
          </div>
          <div class="decision-title">${item.titulo}</div>
          <div class="decision-narrative">${item.narrativa}</div>
        </div>
        <div style="margin-top: 12px; display: flex; justify-content: space-between; align-items: center; font-size: 11px; color: var(--text-dim);">
          <span>Prioridade: <strong style="color: white;">${item.prioridade}</strong></span>
          <button class="btn btn-secondary btn-sm" onclick="openSimulatorModal()">Simular Ação →</button>
        </div>
      `;
      grid.appendChild(card);
    });
  } catch (e) {
    console.error("Error fetching decisions", e);
  }
}

// 3. Trends Chart
async function fetchTrendData(query) {
  try {
    const resp = await fetch(`/api/metrics/trends?${query}`, {
      headers: { "Authorization": `Bearer ${token}` }
    });
    if (!resp.ok) return;
    const data = await resp.json();

    const ctx = document.getElementById("trendChart").getContext("2d");
    if (trendChartInstance) {
      trendChartInstance.destroy();
    }

    trendChartInstance = new Chart(ctx, {
      type: "bar",
      data: {
        labels: data.labels,
        datasets: [
          {
            label: "Pago (R$)",
            data: data.pago,
            backgroundColor: "rgba(16, 185, 129, 0.75)",
            borderColor: "#10b981",
            borderWidth: 1,
            borderRadius: 4,
            order: 2,
            yAxisID: "y"
          },
          {
            label: "Liquidado (R$)",
            data: data.liquidado,
            backgroundColor: "rgba(139, 92, 246, 0.5)",
            borderColor: "#8b5cf6",
            borderWidth: 1,
            borderRadius: 4,
            order: 3,
            yAxisID: "y"
          },
          {
            label: "SLA Médio (Dias)",
            data: data.sla_medio,
            type: "line",
            borderColor: "#fbbf24",
            backgroundColor: "#fbbf24",
            borderWidth: 2.5,
            pointRadius: 4,
            pointHoverRadius: 6,
            tension: 0.3,
            order: 1,
            yAxisID: "y1"
          }
        ]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        interaction: { mode: "index", intersect: false },
        plugins: {
          legend: {
            position: "top",
            labels: { color: "#94a3b8", font: { size: 11, weight: 600 } }
          },
          tooltip: {
            callbacks: {
              label: function(ctx) {
                if (ctx.dataset.yAxisID === "y1") {
                  return `${ctx.dataset.label}: ${ctx.raw} dias`;
                }
                return `${ctx.dataset.label}: ${formatBRL(ctx.raw)}`;
              }
            }
          }
        },
        scales: {
          x: {
            grid: { color: "rgba(255, 255, 255, 0.04)" },
            ticks: { color: "#94a3b8", font: { size: 10 } }
          },
          y: {
            type: "linear",
            display: true,
            position: "left",
            grid: { color: "rgba(255, 255, 255, 0.05)" },
            ticks: {
              color: "#94a3b8",
              font: { size: 10 },
              callback: (v) => "R$ " + (v >= 1e6 ? (v / 1e6).toFixed(1) + "M" : (v / 1e3).toFixed(0) + "k")
            }
          },
          y1: {
            type: "linear",
            display: true,
            position: "right",
            grid: { drawOnChartArea: false },
            ticks: {
              color: "#fbbf24",
              font: { size: 10 },
              callback: (v) => v + "d"
            }
          }
        }
      }
    });
  } catch (e) {
    console.error("Error rendering trend chart", e);
  }
}

// 4. Pareto Chart
async function fetchParetoData(query) {
  try {
    const resp = await fetch(`/api/metrics/pareto?${query}`, {
      headers: { "Authorization": `Bearer ${token}` }
    });
    if (!resp.ok) return;
    const data = await resp.json();

    const ctx = document.getElementById("paretoChart").getContext("2d");
    if (paretoChartInstance) {
      paretoChartInstance.destroy();
    }

    paretoChartInstance = new Chart(ctx, {
      type: "bar",
      data: {
        labels: data.labels.map(l => l.length > 18 ? l.substring(0, 18) + '...' : l),
        datasets: [
          {
            label: "Gasto (R$)",
            data: data.valores,
            backgroundColor: "rgba(59, 130, 246, 0.7)",
            borderColor: "#3b82f6",
            borderWidth: 1,
            borderRadius: 4,
            yAxisID: "y",
            order: 2
          },
          {
            label: "% Acumulado",
            data: data.percentual_acumulado,
            type: "line",
            borderColor: "#f43f5e",
            backgroundColor: "#f43f5e",
            borderWidth: 2,
            pointRadius: 3,
            yAxisID: "y1",
            order: 1
          }
        ]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: {
            position: "top",
            labels: { color: "#94a3b8", font: { size: 11, weight: 600 } }
          },
          tooltip: {
            callbacks: {
              label: function(ctx) {
                if (ctx.dataset.yAxisID === "y1") {
                  return `${ctx.dataset.label}: ${ctx.raw}%`;
                }
                return `${ctx.dataset.label}: ${formatBRL(ctx.raw)}`;
              }
            }
          }
        },
        scales: {
          x: {
            grid: { color: "rgba(255, 255, 255, 0.04)" },
            ticks: { color: "#94a3b8", font: { size: 10 } }
          },
          y: {
            grid: { color: "rgba(255, 255, 255, 0.05)" },
            ticks: {
              color: "#94a3b8",
              font: { size: 10 },
              callback: (v) => "R$ " + (v >= 1e6 ? (v / 1e6).toFixed(0) + "M" : (v / 1e3).toFixed(0) + "k")
            }
          },
          y1: {
            position: "right",
            max: 100,
            min: 0,
            grid: { drawOnChartArea: false },
            ticks: {
              color: "#f43f5e",
              font: { size: 10 },
              callback: (v) => v + "%"
            }
          }
        }
      }
    });
  } catch (e) {
    console.error("Error rendering pareto chart", e);
  }
}

// 5. Rankings Table
async function fetchRankings(query) {
  try {
    const resp = await fetch(`/api/metrics/rankings?${query}`, {
      headers: { "Authorization": `Bearer ${token}` }
    });
    if (!resp.ok) return;
    currentRankingsData = await resp.json();
    renderRankingTable(currentRankingsData);
  } catch (e) {
    console.error("Error fetching rankings", e);
  }
}

function renderRankingTable(items) {
  const tbody = document.getElementById("rankingTableBody");
  tbody.innerHTML = "";

  if (!items || items.length === 0) {
    tbody.innerHTML = `<tr><td colspan="7" style="text-align: center; padding: 24px; color: var(--text-muted);">Nenhum credor encontrado para os filtros selecionados.</td></tr>`;
    return;
  }

  items.forEach(r => {
    const tr = document.createElement("tr");

    let medalClass = "";
    let rankDisplay = r.posicao;
    if (r.posicao === 1) { medalClass = "top-1"; rankDisplay = "🥇"; }
    else if (r.posicao === 2) { medalClass = "top-2"; rankDisplay = "🥈"; }
    else if (r.posicao === 3) { medalClass = "top-3"; rankDisplay = "🥉"; }

    // SLA Meter Fill color
    let slaFillColor = "#10b981";
    if (r.sla_medio > 25) slaFillColor = "#f43f5e";
    else if (r.sla_medio > 15) slaFillColor = "#f59e0b";
    const slaPercent = Math.min(100, (r.sla_medio / 35) * 100);

    tr.innerHTML = `
      <td><span class="rank-badge ${medalClass}">${rankDisplay}</span></td>
      <td>
        <div class="credor-name-cell" title="${r.credor_completo}">${r.credor_nome}</div>
        <div style="font-size: 11px; color: var(--text-dim);">${r.transacoes} transações registradas</div>
      </td>
      <td style="font-weight: 700; color: white;">${formatBRL(r.total_pago)}</td>
      <td>
        <div class="sla-progress-wrap">
          <span style="font-weight: 600; min-width: 45px;">${r.sla_medio}d</span>
          <div class="sla-meter">
            <div class="sla-fill" style="width: ${slaPercent}%; background: ${slaFillColor};"></div>
          </div>
        </div>
      </td>
      <td>
        <div style="font-weight: 700; color: ${r.score >= 85 ? '#34d399' : (r.score >= 70 ? '#fbbf24' : '#fb7185')};">
          ${r.score} pts
        </div>
      </td>
      <td>
        <span class="status-badge ${r.badge_color}">${r.badge}</span>
      </td>
      <td style="text-align: right;">
        <button class="btn btn-secondary btn-sm" onclick="openCredorDetails('${encodeURIComponent(JSON.stringify(r))}')">Detalhar</button>
      </td>
    `;
    tbody.appendChild(tr);
  });
}

function filterRankingTable() {
  const term = document.getElementById("rankingSearchInput").value.toLowerCase().trim();
  if (!term) {
    renderRankingTable(currentRankingsData);
    return;
  }
  const filtered = currentRankingsData.filter(i => 
    i.credor_nome.toLowerCase().includes(term) || 
    i.credor_completo.toLowerCase().includes(term)
  );
  renderRankingTable(filtered);
}

// 6. Deviations & Bottlenecks
async function fetchDeviations(query) {
  try {
    const resp = await fetch(`/api/metrics/deviations?${query}`, {
      headers: { "Authorization": `Bearer ${token}` }
    });
    if (!resp.ok) return;
    const deviations = await resp.json();

    const grid = document.getElementById("deviationsGrid");
    grid.innerHTML = "";

    if (deviations.length === 0) {
      grid.innerHTML = `<div style="grid-column: 1/-1; padding: 20px; background: var(--bg-surface); border-radius: var(--radius-md); text-align: center; color: var(--emerald);">Nenhum desvio crítico detectado para o recorte atual.</div>`;
      return;
    }

    deviations.forEach(d => {
      const card = document.createElement("div");
      card.className = `deviation-card ${d.cor}`;
      card.innerHTML = `
        <div class="deviation-top">
          <span class="deviation-type">${d.tipo}</span>
          <span class="status-badge ${d.cor}">${d.severidade}</span>
        </div>
        <div class="deviation-title">${d.titulo}</div>
        <div class="deviation-desc">${d.descricao}</div>
        <div class="deviation-action-pill">
          💡 <strong>Ação Recomendada:</strong> ${d.acao_sugerida}
        </div>
      `;
      grid.appendChild(card);
    });
  } catch (e) {
    console.error("Error fetching deviations", e);
  }
}

// Credor Details Modal
function openCredorDetails(encodedData) {
  const credor = JSON.parse(decodeURIComponent(encodedData));
  document.getElementById("credorModalName").textContent = credor.credor_nome;

  const body = document.getElementById("credorModalBody");
  body.innerHTML = `
    <div style="margin-bottom: 14px; font-size: 12px; color: var(--text-dim); word-break: break-all;">
      <strong>Razão Social / Cadastro:</strong> ${credor.credor_completo}
    </div>

    <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 12px; margin-bottom: 16px;">
      <div style="background: var(--bg-card); padding: 12px; border-radius: var(--radius-sm); border: 1px solid var(--border-color);">
        <div style="font-size: 11px; color: var(--text-muted);">Total Executado (Pago):</div>
        <div style="font-size: 16px; font-weight: 700; color: white;">${formatBRL(credor.total_pago)}</div>
      </div>
      <div style="background: var(--bg-card); padding: 12px; border-radius: var(--radius-sm); border: 1px solid var(--border-color);">
        <div style="font-size: 11px; color: var(--text-muted);">SLA Médio de Pagamento:</div>
        <div style="font-size: 16px; font-weight: 700; color: ${credor.sla_medio > 20 ? '#fb7185' : '#34d399'};">${credor.sla_medio} dias</div>
      </div>
      <div style="background: var(--bg-card); padding: 12px; border-radius: var(--radius-sm); border: 1px solid var(--border-color);">
        <div style="font-size: 11px; color: var(--text-muted);">Score Operacional:</div>
        <div style="font-size: 16px; font-weight: 700; color: #60a5fa;">${credor.score} / 100</div>
      </div>
      <div style="background: var(--bg-card); padding: 12px; border-radius: var(--radius-sm); border: 1px solid var(--border-color);">
        <div style="font-size: 11px; color: var(--text-muted);">Classificação de Risco:</div>
        <span class="status-badge ${credor.badge_color}">${credor.badge}</span>
      </div>
    </div>

    <div style="background: rgba(30, 41, 59, 0.5); padding: 12px; border-radius: var(--radius-sm); border-left: 3px solid var(--primary); font-size: 12px; color: #cbd5e1;">
      <strong>Diagnóstico Operacional:</strong>
      ${credor.sla_medio <= 15 
        ? "Fornecedor com excelente conformidade nos prazos de ateste e liquidação bancária. Baixo risco operacional." 
        : "Fornecedor apresenta tempo de liquidação acima da meta setorial (15 dias). Recomenda-se conferência das faturas e revisão de processos de ateste."}
    </div>
  `;

  document.getElementById("credorModal").classList.add("active");
}

function closeCredorModal() {
  document.getElementById("credorModal").classList.remove("active");
}

// Drag & Drop File Upload Handler
function setupDragAndDrop() {
  const box = document.getElementById("dropzoneBox");

  ['dragenter', 'dragover'].forEach(name => {
    box.addEventListener(name, (e) => {
      e.preventDefault();
      box.classList.add("dragover");
    });
  });

  ['dragleave', 'drop'].forEach(name => {
    box.addEventListener(name, (e) => {
      e.preventDefault();
      box.classList.remove("dragover");
    });
  });

  box.addEventListener("drop", (e) => {
    const files = e.dataTransfer.files;
    if (files.length > 0) {
      uploadFile(files[0]);
    }
  });
}

function handleFileSelect(e) {
  const files = e.target.files;
  if (files.length > 0) {
    uploadFile(files[0]);
  }
}

async function uploadFile(file) {
  const progressBox = document.getElementById("uploadProgressBox");
  const fileNameText = document.getElementById("uploadFileName");
  const statusText = document.getElementById("uploadStatusText");
  const dropzoneBox = document.getElementById("dropzoneBox");

  fileNameText.textContent = file.name;
  statusText.textContent = "Enviando e processando com Pandas...";
  dropzoneBox.style.display = "none";
  progressBox.style.display = "block";

  const formData = new FormData();
  formData.append("file", file);

  try {
    const resp = await fetch("/api/data/upload", {
      method: "POST",
      headers: { "Authorization": `Bearer ${token}` },
      body: formData
    });
    const res = await resp.json();

    if (resp.ok && res.success) {
      showToast(`Arquivo '${file.name}' processado com sucesso!`, "success");
      closeUploadModal();
      await refreshDashboard();
    } else {
      showToast(res.detail || "Erro no processamento do arquivo", "error");
    }
  } catch (err) {
    showToast("Falha de conexão durante o upload", "error");
  } finally {
    progressBox.style.display = "none";
    dropzoneBox.style.display = "block";
    document.getElementById("fileUploadInput").value = "";
  }
}

function openUploadModal() {
  document.getElementById("uploadModal").classList.add("active");
}

function closeUploadModal() {
  document.getElementById("uploadModal").classList.remove("active");
}

// Google Sheets Sync
function openSyncModal() {
  document.getElementById("syncStatusFeedback").style.display = "none";
  document.getElementById("syncModal").classList.add("active");
}

function closeSyncModal() {
  document.getElementById("syncModal").classList.remove("active");
}

async function triggerGoogleSync() {
  const btn = document.getElementById("btnTriggerSync");
  const feedback = document.getElementById("syncStatusFeedback");
  btn.disabled = true;
  btn.innerHTML = "<span>Sincronizando...</span>";

  try {
    const resp = await fetch("/api/data/sync-google-sheets", {
      method: "POST",
      headers: { "Authorization": `Bearer ${token}` }
    });
    const res = await resp.json();

    if (resp.ok && res.success) {
      feedback.textContent = `✅ ${res.message} (${formatNumber(res.records)} registros carregados).`;
      feedback.style.display = "block";
      showToast("Sincronização com o Google Sheets concluída!", "success");
      await refreshDashboard();
      setTimeout(closeSyncModal, 1500);
    } else {
      feedback.textContent = `❌ ${res.detail || "Erro na sincronização"}`;
      feedback.style.color = "#fb7185";
      feedback.style.display = "block";
    }
  } catch (err) {
    feedback.textContent = "❌ Falha na conexão com o servidor.";
    feedback.style.color = "#fb7185";
    feedback.style.display = "block";
  } finally {
    btn.disabled = false;
    btn.innerHTML = "<span>Iniciar Sincronização</span><span>→</span>";
  }
}

// What-If Scenario Simulator
function openSimulatorModal() {
  document.getElementById("simulatorModal").classList.add("active");
  runScenarioSimulation();
}

function closeSimulatorModal() {
  document.getElementById("simulatorModal").classList.remove("active");
}

async function runScenarioSimulation() {
  const costVal = parseFloat(document.getElementById("sliderCost").value);
  const slaVal = parseFloat(document.getElementById("sliderSla").value);

  document.getElementById("sliderCostLabel").textContent = `${costVal.toFixed(1)}%`;
  document.getElementById("sliderSlaLabel").textContent = `${slaVal.toFixed(1)}%`;

  try {
    const resp = await fetch("/api/decisions/simulate", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "Authorization": `Bearer ${token}`
      },
      body: JSON.stringify({
        cost_reduction_pct: costVal,
        sla_improvement_pct: slaVal
      })
    });
    if (!resp.ok) return;
    const res = await resp.json();

    document.getElementById("simSavings").textContent = formatBRL(res.economia_projetada_reais);
    document.getElementById("simDaysSaved").textContent = `${res.dias_poupados_ciclo} dias`;
    document.getElementById("simNewSLA").textContent = `${res.novo_sla_projetado} dias`;
    document.getElementById("simIgeoGain").textContent = `+${res.ganho_pontos_igeo} pts`;
  } catch (e) {
    console.error("Error in simulation", e);
  }
}

// Export CSV
function exportReport() {
  window.open("/api/data/export?format=csv", "_blank");
}

// Auto-Refresh Poll for Background Automated Watcher
function setupAutoRefreshPoll() {
  let lastSeenTime = null;
  setInterval(async () => {
    try {
      const resp = await fetch("/api/data/status");
      if (!resp.ok) return;
      const data = await resp.json();

      if (lastSeenTime && lastSeenTime !== data.last_updated) {
        showToast(`Base atualizada automaticamente: ${formatNumber(data.total_records)} registros`, "info");
        await refreshDashboard();
      }
      lastSeenTime = data.last_updated;
    } catch (e) {
      // background polling
    }
  }, 12000); // 12 seconds
}
