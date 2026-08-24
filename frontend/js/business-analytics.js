const API_BASE_URL = 'http://127.0.0.1:8000';

let currentDatasetId = null;
let chartInstances = [];

document.addEventListener('DOMContentLoaded', () => {
    checkAuth();
    loadUserProfile();
    bindEvents();
    loadPastDatasets();
});

function checkAuth() {
    const token = localStorage.getItem('access_token');
    if (!token) {
        window.location.href = 'login.html';
    }
}

function loadUserProfile() {
    const userStr = localStorage.getItem('user_data');
    if (userStr) {
        try {
            const user = JSON.parse(userStr);
            const name = user.full_name || 'User';
            document.getElementById('sidebarUserName').textContent = name;
            document.getElementById('sidebarUserRole').textContent = (user.role || 'User').toUpperCase();
            document.getElementById('sidebarUserAvatar').textContent = name.charAt(0).toUpperCase();
        } catch (e) {
            console.error('Error parsing user_data:', e);
        }
    }
}

function bindEvents() {
    const logoutBtn = document.getElementById('logoutBtn');
    if (logoutBtn) {
        logoutBtn.addEventListener('click', () => {
            localStorage.removeItem('access_token');
            localStorage.removeItem('user_data');
            window.location.href = 'login.html';
        });
    }

    const fileInput = document.getElementById('businessFileInput');
    if (fileInput) {
        fileInput.addEventListener('change', (e) => {
            if (e.target.files.length > 0) {
                uploadBusinessFile(e.target.files[0]);
            }
        });
    }

    const askForm = document.getElementById('askDataForm');
    if (askForm) {
        askForm.addEventListener('submit', (e) => {
            e.preventDefault();
            const q = document.getElementById('dataQuestionInput').value.trim();
            if (q) askDatasetQuestion(q);
        });
    }

    // Quick suggestion pills
    document.querySelectorAll('.pill-question').forEach((pill) => {
        pill.addEventListener('click', () => {
            const q = pill.dataset.q;
            document.getElementById('dataQuestionInput').value = q;
            askDatasetQuestion(q);
        });
    });

    const btnPdf = document.getElementById('btnDownloadPdfReport');
    if (btnPdf) {
        btnPdf.addEventListener('click', downloadPdfReport);
    }

    const pastSelect = document.getElementById('selectPastDataset');
    if (pastSelect) {
        pastSelect.addEventListener('change', (e) => {
            const id = Number(e.target.value);
            if (id) fetchDatasetDetails(id);
        });
    }
}

async function uploadBusinessFile(file) {
    const token = localStorage.getItem('access_token');
    const statusBox = document.getElementById('uploadStatusBox');
    const statusFileName = document.getElementById('statusFileName');
    const statusText = document.getElementById('statusText');
    const spinner = document.getElementById('statusSpinner');
    const resultsSection = document.getElementById('analysisResultsSection');

    statusBox.classList.remove('d-none');
    spinner.classList.remove('d-none');
    statusFileName.textContent = `File: ${file.name}`;
    statusText.textContent = 'Status: Uploading and analyzing data with AI...';

    const formData = new FormData();
    formData.append('file', file);

    try {
        const response = await fetch(`${API_BASE_URL}/api/business-analytics/upload`, {
            method: 'POST',
            headers: { 'Authorization': `Bearer ${token}` },
            body: formData
        });

        const data = await response.json();
        if (!response.ok) throw new Error(data.detail || 'Failed to analyze business data.');

        spinner.classList.add('d-none');
        statusText.innerHTML = '<span class="text-success fw-bold"><i class="fas fa-check-circle me-1"></i> Analysis completed</span>';

        currentDatasetId = data.id;
        renderAnalysisResults(data);
        resultsSection.classList.remove('d-none');
        loadPastDatasets();
    } catch (error) {
        spinner.classList.add('d-none');
        statusText.innerHTML = `<span class="text-danger"><i class="fas fa-exclamation-circle me-1"></i> Error: ${escapeHtml(error.message)}</span>`;
    }
}

async function loadPastDatasets() {
    const token = localStorage.getItem('access_token');
    const pastSelect = document.getElementById('selectPastDataset');
    if (!pastSelect) return;

    try {
        const response = await fetch(`${API_BASE_URL}/api/business-analytics/datasets`, {
            headers: { 'Authorization': `Bearer ${token}` }
        });
        if (!response.ok) return;
        const datasets = await response.json();

        pastSelect.innerHTML = '<option value="">-- Load Past Dataset --</option>' + datasets.map((d) => `
            <option value="${d.id}">${escapeHtml(d.filename)} (${d.file_type})</option>
        `).join('');
    } catch (e) {
        console.error('Error loading past datasets:', e);
    }
}

async function fetchDatasetDetails(id) {
    const token = localStorage.getItem('access_token');
    const resultsSection = document.getElementById('analysisResultsSection');

    try {
        const response = await fetch(`${API_BASE_URL}/api/business-analytics/datasets/${id}`, {
            headers: { 'Authorization': `Bearer ${token}` }
        });
        if (!response.ok) throw new Error('Unable to fetch dataset.');
        const data = await response.json();

        currentDatasetId = data.id;
        renderAnalysisResults(data);
        resultsSection.classList.remove('d-none');
    } catch (error) {
        alert(error.message);
    }
}

function renderAnalysisResults(data) {
    // 1. KPI Statistics
    const statsContainer = document.getElementById('statsCardsContainer');
    const stats = data.key_stats || {};
    
    if (Object.keys(stats).length === 0) {
        statsContainer.innerHTML = '<div class="col-12 text-muted">No statistics extracted.</div>';
    } else {
        statsContainer.innerHTML = Object.entries(stats).map(([label, val]) => `
            <div class="col-6 col-md-3">
                <div class="stat-card">
                    <div class="stat-label text-truncate" title="${escapeHtml(label)}">${escapeHtml(label)}</div>
                    <div class="stat-val">${escapeHtml(String(val))}</div>
                </div>
            </div>
        `).join('');
    }

    // 2. Visual Charts
    renderCharts(data.charts_config || []);

    // 3. Key Insights
    const insightsList = document.getElementById('insightsList');
    const insights = data.insights || [];

    if (insights.length === 0) {
        insightsList.innerHTML = '<li>Data analyzed successfully. No specific trend detected.</li>';
    } else {
        insightsList.innerHTML = insights.map((item) => `<li>${escapeHtml(item)}</li>`).join('');
    }

    // Reset Chat Box
    document.getElementById('chatAnswerBox').classList.add('d-none');
}

function renderCharts(configs) {
    const container = document.getElementById('chartsContainer');
    if (!container) return;

    // Destroy existing chart instances
    chartInstances.forEach((chart) => chart.destroy());
    chartInstances = [];

    if (!Array.isArray(configs) || configs.length === 0) {
        container.innerHTML = '';
        return;
    }

    container.innerHTML = configs.map((cfg, idx) => `
        <div class="col-lg-6">
            <div class="card border-0 shadow-sm rounded-4 p-3 h-100">
                <h6 class="fw-bold text-dark mb-3"><i class="fas fa-chart-bar text-primary me-2"></i> ${escapeHtml(cfg.title || 'Chart')}</h6>
                <div style="position: relative; height: 260px;">
                    <canvas id="canvas_chart_${idx}"></canvas>
                </div>
            </div>
        </div>
    `).join('');

    // Instantiate Chart.js
    configs.forEach((cfg, idx) => {
        const canvas = document.getElementById(`canvas_chart_${idx}`);
        if (!canvas) return;

        const chart = new Chart(canvas, {
            type: cfg.type || 'bar',
            data: {
                labels: cfg.labels || [],
                datasets: [{
                    label: cfg.title || 'Value',
                    data: cfg.data || [],
                    backgroundColor: cfg.type === 'line' ? 'rgba(37, 99, 235, 0.1)' : ['#2563eb', '#7c3aed', '#0284c7', '#16a34a', '#d97706', '#dc2626'],
                    borderColor: '#2563eb',
                    borderWidth: 2,
                    fill: cfg.type === 'line',
                    tension: 0.3
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: { legend: { display: false } },
                scales: {
                    x: { grid: { display: false } },
                    y: { beginAtZero: true }
                }
            }
        });
        chartInstances.push(chart);
    });
}

async function askDatasetQuestion(question) {
    if (!currentDatasetId) {
        alert('Please upload or load a business dataset first.');
        return;
    }

    const token = localStorage.getItem('access_token');
    const btnAsk = document.getElementById('btnAskData');
    const answerBox = document.getElementById('chatAnswerBox');
    const qText = document.getElementById('chatQuestionText');
    const aText = document.getElementById('chatAnswerText');

    btnAsk.disabled = true;
    btnAsk.innerHTML = '<span class="spinner-border spinner-border-sm me-1"></span> Analyzing...';

    answerBox.classList.remove('d-none');
    qText.textContent = `Question: ${question}`;
    aText.innerHTML = '<span class="text-muted"><i class="fas fa-robot me-1"></i> Grounding query against actual dataset values...</span>';

    try {
        const response = await fetch(`${API_BASE_URL}/api/business-analytics/datasets/${currentDatasetId}/ask`, {
            method: 'POST',
            headers: {
                'Authorization': `Bearer ${token}`,
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ question: question })
        });

        const data = await response.json();
        if (!response.ok) throw new Error(data.detail || 'Unable to answer question.');

        aText.textContent = data.answer;
    } catch (error) {
        aText.innerHTML = `<span class="text-danger">${escapeHtml(error.message)}</span>`;
    } finally {
        btnAsk.disabled = false;
        btnAsk.innerHTML = '<i class="fas fa-paper-plane me-1"></i> Ask';
    }
}

async function downloadPdfReport() {
    if (!currentDatasetId) {
        alert('Please upload or load a dataset first.');
        return;
    }

    const token = localStorage.getItem('access_token');
    try {
        const response = await fetch(`${API_BASE_URL}/api/business-analytics/datasets/${currentDatasetId}/pdf`, {
            headers: { 'Authorization': `Bearer ${token}` }
        });

        if (!response.ok) throw new Error('Unable to download PDF report.');

        const blob = await response.blob();
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `Business_Report_Dataset_${currentDatasetId}.pdf`;
        document.body.appendChild(a);
        a.click();
        a.remove();
        window.URL.revokeObjectURL(url);
    } catch (error) {
        alert(error.message);
    }
}

function escapeHtml(str) {
    return String(str ?? '').replace(/[&<>"']/g, (char) => ({
        '&': '&amp;',
        '<': '&lt;',
        '>': '&gt;',
        '"': '&quot;',
        "'": '&#39;'
    }[char]));
}
