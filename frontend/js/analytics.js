const API_BASE_URL = "https://intellibusiness-db.onrender.com";

let selectedPeriod = '7d';

// Chart instances
let chartAiQuestions = null;
let chartDocStatus = null;
let chartFeatureBreakdown = null;
let chartEmailDelivery = null;
let chartWorkflowStatus = null;

document.addEventListener('DOMContentLoaded', () => {
    checkAuth();
    loadUserProfile();
    bindEvents();
    loadAllAnalytics(selectedPeriod);
});

function checkAuth() {
    const token = localStorage.getItem('access_token');
    if (!token) {
        window.location.href = 'login.html';
    }
}

function loadUserProfile() {
    const userStr = localStorage.getItem('user') || localStorage.getItem('user_data');
    if (userStr) {
        try {
            const user = JSON.parse(userStr);
            const name = user.full_name || 'User';
            document.getElementById('profileModalName').textContent = name;
            document.getElementById('profileModalCompany').textContent = user.company_name || '-';
            document.getElementById('profileModalEmail').textContent = user.email || '-';
            document.getElementById('profileModalAvatar').textContent = name.charAt(0).toUpperCase();
        } catch (e) {
            console.error('Error parsing user_data:', e);
        }
    }
}

function bindEvents() {
    const logoutBtn = document.getElementById('btnLogoutSidebar');
    if (logoutBtn) {
        logoutBtn.addEventListener('click', () => {
            localStorage.removeItem('access_token');
            localStorage.removeItem('user');
            localStorage.removeItem('user_data');
            window.location.href = 'login.html';
        });
    }

    // Time Period Filter Pills
    const periodPills = document.querySelectorAll('#periodPillGroup .period-pill');
    periodPills.forEach((pill) => {
        pill.addEventListener('click', () => {
            periodPills.forEach((p) => p.classList.remove('active'));
            pill.classList.add('active');
            selectedPeriod = pill.dataset.period || '7d';
            
            // Update time period badge
            const badge = document.getElementById('chartTimePeriodBadge');
            if (badge) badge.textContent = pill.textContent;

            loadAllAnalytics(selectedPeriod);
        });
    });
}

async function loadAllAnalytics(period) {
    const token = localStorage.getItem('access_token');
    
    // Load in parallel
    loadOverviewKPIs(token, period);
    loadDocumentAnalytics(token, period);
    loadAiUsageAnalytics(token, period);
    loadEmailAnalytics(token, period);
    loadWorkflowAnalytics(token, period);
    loadActivityStream(token, period);
}

// 1. OVERVIEW KPIS
async function loadOverviewKPIs(token, period) {
    try {
        const res = await fetch(`${API_BASE_URL}/api/analytics/overview?period=${period}`, {
            headers: { 'Authorization': `Bearer ${token}` }
        });
        if (!res.ok) return;
        const data = await res.json();

        animateCounter('kpiTotalDocs', data.total_documents || 0);
        document.getElementById('kpiProcessedSub').textContent = `${data.processed_documents || 0} Processed`;

        animateCounter('kpiTotalSummaries', data.total_summaries || 0);
        animateCounter('kpiChatQuestions', data.chat_questions || 0);

        animateCounter('kpiEmailsGenerated', data.emails_generated || 0);
        document.getElementById('kpiEmailsSentSub').textContent = `${data.emails_sent || 0} Sent`;

        animateCounter('kpiActiveWorkflows', data.active_workflows || 0);
    } catch (e) {
        console.error('Error loading overview KPIs:', e);
    }
}

// 2. DOCUMENT ANALYTICS & RECENT UPLOADS TABLE
async function loadDocumentAnalytics(token, period) {
    try {
        const res = await fetch(`${API_BASE_URL}/api/analytics/documents?period=${period}`, {
            headers: { 'Authorization': `Bearer ${token}` }
        });
        if (!res.ok) return;
        const data = await res.json();

        // Render Doughnut Chart for Document Status
        const dist = data.status_distribution || {};
        renderDocStatusChart(dist.completed || 0, dist.processing || 0, dist.failed || 0);

        // Render Recent Uploads Table
        renderRecentDocsTable(data.recent_uploads || []);
    } catch (e) {
        console.error('Error loading document analytics:', e);
    }
}

// 3. AI USAGE ANALYTICS (LINE CHART & BAR CHART)
async function loadAiUsageAnalytics(token, period) {
    try {
        const res = await fetch(`${API_BASE_URL}/api/analytics/ai-usage?period=${period}`, {
            headers: { 'Authorization': `Bearer ${token}` }
        });
        if (!res.ok) return;
        const data = await res.json();

        // AI Questions Line Chart
        const series = data.questions_series || {};
        renderAiQuestionsChart(series.labels || [], series.data || []);

        // Feature Breakdown Bar Chart
        const breakdown = data.feature_breakdown || {};
        renderFeatureBreakdownChart(breakdown);
    } catch (e) {
        console.error('Error loading AI usage analytics:', e);
    }
}

// 4. EMAIL ANALYTICS
async function loadEmailAnalytics(token, period) {
    try {
        const res = await fetch(`${API_BASE_URL}/api/analytics/emails?period=${period}`, {
            headers: { 'Authorization': `Bearer ${token}` }
        });
        if (!res.ok) return;
        const data = await res.json();

        const series = data.time_series || {};
        renderEmailDeliveryChart(series.labels || [], series.data || []);
    } catch (e) {
        console.error('Error loading email analytics:', e);
    }
}

// 5. WORKFLOW ANALYTICS
async function loadWorkflowAnalytics(token, period) {
    try {
        const res = await fetch(`${API_BASE_URL}/api/analytics/workflows?period=${period}`, {
            headers: { 'Authorization': `Bearer ${token}` }
        });
        if (!res.ok) return;
        const data = await res.json();

        const dist = data.status_distribution || {};
        renderWorkflowStatusChart(dist.completed || 0, dist.failed || 0, dist.running || 0);
    } catch (e) {
        console.error('Error loading workflow analytics:', e);
    }
}

// 6. RECENT ACTIVITY STREAM
async function loadActivityStream(token, period) {
    const container = document.getElementById('activityStreamContainer');
    if (!container) return;

    try {
        const res = await fetch(`${API_BASE_URL}/api/analytics/activity?period=${period}`, {
            headers: { 'Authorization': `Bearer ${token}` }
        });
        if (!res.ok) throw new Error('Unable to load activity log.');
        const activities = await res.json();

        renderActivityStream(container, activities);
    } catch (e) {
        container.innerHTML = `<div class="text-center py-4 text-muted small">No recent activity for selected period.</div>`;
    }
}

// ============================================
// CHART.JS RENDERING FUNCTIONS
// ============================================

function renderAiQuestionsChart(labels, data) {
    const ctx = document.getElementById('aiQuestionsChart');
    if (!ctx) return;

    if (chartAiQuestions) chartAiQuestions.destroy();

    chartAiQuestions = new Chart(ctx, {
        type: 'line',
        data: {
            labels: labels,
            datasets: [{
                label: 'AI Chat Queries',
                data: data,
                borderColor: '#2563eb',
                backgroundColor: 'rgba(37, 99, 235, 0.1)',
                borderWidth: 2,
                fill: true,
                tension: 0.35,
                pointRadius: 4,
                pointBackgroundColor: '#2563eb'
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: { legend: { display: false } },
            scales: {
                x: { grid: { display: false } },
                y: { beginAtZero: true, ticks: { precision: 0 } }
            }
        }
    });
}

function renderDocStatusChart(completed, processing, failed) {
    const ctx = document.getElementById('docStatusChart');
    if (!ctx) return;

    if (chartDocStatus) chartDocStatus.destroy();

    const hasData = (completed + processing + failed) > 0;
    const chartData = hasData ? [completed, processing, failed] : [1];
    const chartColors = hasData ? ['#16a34a', '#0284c7', '#dc2626'] : ['#e2e8f0'];
    const chartLabels = hasData ? ['Completed', 'Processing', 'Failed'] : ['No Data'];

    chartDocStatus = new Chart(ctx, {
        type: 'doughnut',
        data: {
            labels: chartLabels,
            datasets: [{
                data: chartData,
                backgroundColor: chartColors,
                borderWidth: 0
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { position: 'bottom', labels: { boxWidth: 10, usePointStyle: true } }
            },
            cutout: '70%'
        }
    });
}

function renderFeatureBreakdownChart(breakdown) {
    const ctx = document.getElementById('featureBreakdownChart');
    if (!ctx) return;

    if (chartFeatureBreakdown) chartFeatureBreakdown.destroy();

    const labels = Object.keys(breakdown);
    const values = Object.values(breakdown);

    chartFeatureBreakdown = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: labels,
            datasets: [{
                label: 'Usage Count',
                data: values,
                backgroundColor: ['#2563eb', '#7c3aed', '#0284c7'],
                borderRadius: 6
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: { legend: { display: false } },
            scales: {
                x: { grid: { display: false } },
                y: { beginAtZero: true, ticks: { precision: 0 } }
            }
        }
    });
}

function renderEmailDeliveryChart(labels, data) {
    const ctx = document.getElementById('emailDeliveryChart');
    if (!ctx) return;

    if (chartEmailDelivery) chartEmailDelivery.destroy();

    chartEmailDelivery = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: labels,
            datasets: [{
                label: 'Emails Sent',
                data: data,
                backgroundColor: '#16a34a',
                borderRadius: 6
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: { legend: { display: false } },
            scales: {
                x: { grid: { display: false } },
                y: { beginAtZero: true, ticks: { precision: 0 } }
            }
        }
    });
}

function renderWorkflowStatusChart(completed, failed, running) {
    const ctx = document.getElementById('workflowStatusChart');
    if (!ctx) return;

    if (chartWorkflowStatus) chartWorkflowStatus.destroy();

    const hasData = (completed + failed + running) > 0;
    const chartData = hasData ? [completed, failed, running] : [1];
    const chartColors = hasData ? ['#16a34a', '#dc2626', '#0284c7'] : ['#e2e8f0'];
    const chartLabels = hasData ? ['Completed', 'Failed', 'Running'] : ['No Runs'];

    chartWorkflowStatus = new Chart(ctx, {
        type: 'doughnut',
        data: {
            labels: chartLabels,
            datasets: [{
                data: chartData,
                backgroundColor: chartColors,
                borderWidth: 0
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { position: 'bottom', labels: { boxWidth: 10, usePointStyle: true } }
            },
            cutout: '70%'
        }
    });
}

// ============================================
// HELPER TABLE & STREAM RENDERERS
// ============================================

function renderRecentDocsTable(docs) {
    const tbody = document.getElementById('recentDocsTableBody');
    if (!tbody) return;

    if (!Array.isArray(docs) || docs.length === 0) {
        tbody.innerHTML = '<tr><td colspan="5" class="text-center text-muted py-4">No uploaded documents found.</td></tr>';
        return;
    }

    tbody.innerHTML = docs.map((doc) => {
        let badgeClass = 'bg-secondary-subtle text-secondary';
        if (doc.status === 'completed') badgeClass = 'bg-success-subtle text-success';
        else if (doc.status === 'failed') badgeClass = 'bg-danger-subtle text-danger';
        else if (doc.status === 'processing') badgeClass = 'bg-info-subtle text-info';

        return `
            <tr>
                <td class="fw-semibold text-dark text-truncate" style="max-width: 160px;" title="${escapeHtml(doc.filename)}">
                    <i class="fas fa-file-pdf text-primary me-1"></i> ${escapeHtml(doc.filename)}
                </td>
                <td><span class="badge bg-light text-dark border">${escapeHtml(doc.file_type)}</span></td>
                <td>${doc.file_size} KB</td>
                <td><span class="badge ${badgeClass} text-capitalize">${escapeHtml(doc.status)}</span></td>
                <td class="text-muted">${escapeHtml(doc.upload_date)}</td>
            </tr>
        `;
    }).join('');
}

function renderActivityStream(container, activities) {
    if (!Array.isArray(activities) || activities.length === 0) {
        container.innerHTML = '<div class="text-center py-4 text-muted small">No activity found for this period.</div>';
        return;
    }

    container.innerHTML = activities.map((act) => `
        <div class="activity-stream-item">
            <div class="activity-icon-badge ${act.bg_color || 'bg-light'} ${act.icon_color || 'text-primary'}">
                <i class="${act.icon || 'fas fa-circle'}"></i>
            </div>
            <div class="flex-grow-1 min-w-0">
                <div class="d-flex align-items-center justify-content-between mb-1">
                    <span class="fw-semibold text-dark small text-truncate" style="max-width: 250px;">${escapeHtml(act.title)}</span>
                    <small class="text-muted" style="font-size: 0.725rem;"><i class="far fa-clock me-1"></i> ${escapeHtml(act.timestamp)}</small>
                </div>
                <div class="text-muted small text-truncate">${escapeHtml(act.description)}</div>
            </div>
        </div>
    `).join('');
}

function animateCounter(elementId, targetValue) {
    const el = document.getElementById(elementId);
    if (!el) return;

    let start = 0;
    const duration = 800;
    const stepTime = 25;
    const steps = Math.ceil(duration / stepTime);
    const increment = targetValue / steps;

    if (targetValue === 0) {
        el.textContent = 0;
        return;
    }

    const timer = setInterval(() => {
        start += increment;
        if (start >= targetValue) {
            el.textContent = targetValue;
            clearInterval(timer);
        } else {
            el.textContent = Math.floor(start);
        }
    }, stepTime);
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
