const API_BASE_URL = "https://intellibusiness-db.onrender.com"; 
const pageSize = 10;
let currentPage = 1;
let searchTimer;
const charts = {};

window.addEventListener('DOMContentLoaded', initAdminDashboard);

async function initAdminDashboard() {
    const token = localStorage.getItem('access_token');
    if (!token) return redirectToLogin();

    try {
        const profileResponse = await apiFetch('/api/auth/profile');
        if (!profileResponse.ok) return redirectToLogin();
        const profile = await profileResponse.json();
        if (profile.role !== 'admin') {
            window.location.href = 'dashboard.html';
            return;
        }
        document.getElementById('adminName').textContent = profile.full_name || 'Administrator';
        bindAdminEvents();
        await loadAdminData();
    } catch (error) {
        showAlert('Unable to load the admin dashboard.', 'danger');
    }
}

function apiFetch(path, options = {}) {
    return fetch(`${API_BASE_URL}${path}`, {
        ...options,
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${localStorage.getItem('access_token')}`, ...(options.headers || {}) },
    });
}

async function loadAdminData() {
    const [overviewResponse, analyticsResponse] = await Promise.all([
        apiFetch('/api/admin/overview'),
        apiFetch('/api/admin/analytics?days=30'),
    ]);
    if (overviewResponse.status === 403 || analyticsResponse.status === 403) return window.location.href = 'dashboard.html';
    if (!overviewResponse.ok || !analyticsResponse.ok) throw new Error('Admin data request failed');
    renderOverview(await overviewResponse.json());
    renderCharts(await analyticsResponse.json());
    
    // Load users with error handling
    try {
        await loadUsers();
    } catch (error) {
        console.error('Error loading users:', error);
    }
    
    // Load automations with error handling
    try {
        await loadAutomations();
    } catch (error) {
        console.error('Error loading automations:', error);
    }
}

function renderOverview(data) {
    const values = {
        totalUsers: data.total_users,
        activeUsers: data.total_active_users,
        totalWorkflows: data.total_workflows,
        runningWorkflows: data.currently_running_workflows,
        completedWorkflows: data.completed_workflows,
        failedWorkflows: data.failed_workflows,
        totalAiUsage: data.total_ai_usage,
        aiUsagePercentage: `${data.ai_usage_percentage}%`,
    };
    Object.entries(values).forEach(([id, value]) => { document.getElementById(id).textContent = value ?? 0; });
}

function renderCharts(data) {
    createChart('userGrowthChart', 'line', data.labels, [{ label: 'New users', data: data.user_growth, borderColor: '#2563eb', backgroundColor: 'rgba(37,99,235,.12)', fill: true, tension: .3 }]);
    createChart('aiUsageChart', 'bar', data.labels, [{ label: 'AI events', data: data.ai_usage_over_time, backgroundColor: '#0f766e', borderRadius: 4 }]);
    createChart('workflowStatusChart', 'doughnut', Object.keys(data.workflow_status_distribution), [{ data: Object.values(data.workflow_status_distribution), backgroundColor: ['#f59e0b', '#2563eb', '#16a34a', '#dc2626'] }]);
    createChart('workflowActivityChart', 'line', data.labels, [{ label: 'Workflow runs', data: data.workflow_activity, borderColor: '#7c3aed', backgroundColor: 'rgba(124,58,237,.1)', fill: true, tension: .3 }]);
}

function createChart(id, type, labels, datasets) {
    if (charts[id]) charts[id].destroy();
    charts[id] = new Chart(document.getElementById(id), {
        type,
        data: { labels, datasets },
        options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { display: type === 'doughnut', position: 'bottom' } }, scales: type === 'doughnut' ? {} : { y: { beginAtZero: true, ticks: { precision: 0 } } } },
    });
}

async function loadUsers() {
    const params = new URLSearchParams({ page: currentPage, limit: pageSize, search: document.getElementById('userSearch').value.trim() });
    const response = await apiFetch(`/api/admin/users?${params}`);
    if (!response.ok) throw new Error('Users request failed');
    const data = await response.json();
    document.getElementById('userCount').textContent = data.total;
    document.getElementById('pageLabel').textContent = `Page ${data.page}`;
    document.getElementById('previousPage').disabled = currentPage <= 1;
    document.getElementById('nextPage').disabled = currentPage * pageSize >= data.total;
    document.getElementById('usersTable').innerHTML = data.items.length ? data.items.map((user) => `<tr><td>${escapeHtml(user.full_name)}</td><td>${escapeHtml(user.email)}</td><td>${escapeHtml(user.company_name)}</td><td>${new Date(user.created_at).toLocaleDateString()}</td><td><span class="status-pill ${user.status === 'Inactive' ? 'inactive' : ''}">${user.status}</span></td></tr>`).join('') : '<tr><td colspan="5" class="text-center text-muted py-4">No users found.</td></tr>';
}

function bindAdminEvents() {
    document.getElementById('refreshAdmin').addEventListener('click', () => loadAdminData().catch(() => showAlert('Unable to refresh dashboard data.', 'danger')));
    document.getElementById('userSearch').addEventListener('input', () => { clearTimeout(searchTimer); searchTimer = setTimeout(() => { currentPage = 1; loadUsers(); }, 250); });
    document.getElementById('previousPage').addEventListener('click', () => { if (currentPage > 1) { currentPage -= 1; loadUsers(); } });
    document.getElementById('nextPage').addEventListener('click', () => { currentPage += 1; loadUsers(); });
    ['adminLogout', 'adminLogoutMobile'].forEach((id) => document.getElementById(id)?.addEventListener('click', logout));
    document.getElementById('passwordForm').addEventListener('submit', changePassword);
    
    // Bind Save Automation button if it exists
    const saveAutomationBtn = document.getElementById('saveAutomationBtn');
    if (saveAutomationBtn) {
        saveAutomationBtn.addEventListener('click', saveAutomationChanges);
    }
}

async function changePassword(event) {
    event.preventDefault();
    const currentPassword = document.getElementById('currentPassword').value;
    const newPassword = document.getElementById('newPassword').value;
    const confirmPassword = document.getElementById('confirmPassword').value;
    if (newPassword !== confirmPassword) return showPasswordAlert('New passwords do not match.', 'danger');
    const response = await apiFetch('/api/auth/change-password', { method: 'POST', body: JSON.stringify({ current_password: currentPassword, new_password: newPassword, confirm_password: confirmPassword }) });
    const data = await response.json();
    if (!response.ok) return showPasswordAlert(data.detail || 'Unable to change password.', 'danger');
    showPasswordAlert(data.message, 'success');
    document.getElementById('passwordForm').reset();
}

function logout(event) { event.preventDefault(); localStorage.removeItem('access_token'); localStorage.removeItem('user'); localStorage.removeItem('user_data'); redirectToLogin(); }
function redirectToLogin() { window.location.href = 'login.html'; }
function showAlert(message, type) { const alert = document.getElementById('adminAlert'); alert.textContent = message; alert.className = `alert alert-${type}`; }
function showPasswordAlert(message, type) { const alert = document.getElementById('passwordAlert'); alert.textContent = message; alert.className = `alert alert-${type}`; }
function escapeHtml(value) { return String(value ?? '').replace(/[&<>'"]/g, (character) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#39;', '"': '&quot;' }[character])); }

// Admin Automations Functions
async function loadAutomations() {
    try {
        const response = await apiFetch('/api/admin/automations');
        if (!response.ok) throw new Error('Failed to load automations');
        const automations = await response.json();
        renderAutomations(automations);
    } catch (error) {
        console.error('Error loading automations:', error);
        document.getElementById('automationsList').innerHTML = '<div class="text-center text-muted py-4">Failed to load automations.</div>';
    }
}

function renderAutomations(automations) {
    const container = document.getElementById('automationsList');
    
    if (!automations || automations.length === 0) {
        container.innerHTML = '<div class="text-center text-muted py-4">No automations found.</div>';
        return;
    }

    container.innerHTML = automations.map(automation => `
        <div class="automation-card" data-automation-id="${automation.id}">
            <div class="automation-card-header">
                <div>
                    <h4>${escapeHtml(automation.name)}</h4>
                    <p class="text-muted mb-0">Trigger: <code>${escapeHtml(automation.trigger_type)}</code></p>
                </div>
                <div class="automation-status">
                    <label class="form-check form-switch">
                        <input class="form-check-input automation-toggle" type="checkbox" ${automation.is_active ? 'checked' : ''} data-automation-id="${automation.id}">
                        <span class="automation-status-label">${automation.is_active ? 'Active' : 'Inactive'}</span>
                    </label>
                </div>
            </div>

            <div class="automation-card-body">
                <div class="form-group mb-3">
                    <label class="form-label">Email Subject</label>
                    <input type="text" class="form-control automation-subject" value="${escapeHtml(automation.email_subject)}" readonly>
                </div>
                <div class="form-group mb-3">
                    <label class="form-label">Email Template</label>
                    <textarea class="form-control automation-template" rows="6" readonly>${escapeHtml(automation.email_template)}</textarea>
                </div>
            </div>

            <div class="automation-card-actions">
                <button class="btn btn-sm btn-outline-primary edit-automation" data-automation-id="${automation.id}" data-bs-toggle="modal" data-bs-target="#automationModal">
                    <i class="fas fa-edit me-1"></i> Edit
                </button>
                <button class="btn btn-sm btn-outline-secondary test-automation" data-automation-id="${automation.id}">
                    <i class="fas fa-paper-plane me-1"></i> Send Test
                </button>
                <button class="btn btn-sm btn-outline-info view-history" data-automation-id="${automation.id}" data-bs-toggle="modal" data-bs-target="#historyModal">
                    <i class="fas fa-history me-1"></i> History
                </button>
            </div>
        </div>
    `).join('');

    // Bind event listeners
    bindAutomationEvents();
}

function bindAutomationEvents() {
    // Toggle automation active status
    document.querySelectorAll('.automation-toggle').forEach(toggle => {
        toggle.addEventListener('change', toggleAutomation);
    });

    // Edit automation
    document.querySelectorAll('.edit-automation').forEach(btn => {
        btn.addEventListener('click', editAutomation);
    });

    // Test automation
    document.querySelectorAll('.test-automation').forEach(btn => {
        btn.addEventListener('click', testAutomation);
    });

    // View history
    document.querySelectorAll('.view-history').forEach(btn => {
        btn.addEventListener('click', viewAutomationHistory);
    });
}

async function toggleAutomation(event) {
    const automationId = event.target.dataset.automationId;
    const isActive = event.target.checked;
    
    try {
        // First load the automation data
        const response = await apiFetch(`/api/admin/automations`);
        if (!response.ok) throw new Error('Failed to load automation');
        const automations = await response.json();
        const automation = automations.find(a => a.id == automationId);
        
        if (!automation) throw new Error('Automation not found');

        // Update the automation
        const updateResponse = await apiFetch(`/api/admin/automations/${automationId}`, {
            method: 'PUT',
            body: JSON.stringify({
                is_active: isActive,
                email_subject: automation.email_subject,
                email_template: automation.email_template
            })
        });

        if (!updateResponse.ok) {
            event.target.checked = !isActive;
            throw new Error('Failed to update automation');
        }

        // Update UI
        const card = document.querySelector(`[data-automation-id="${automationId}"]`);
        const statusLabel = card.querySelector('.automation-status-label');
        statusLabel.textContent = isActive ? 'Active' : 'Inactive';
    } catch (error) {
        console.error('Error toggling automation:', error);
        showAlert('Failed to update automation status.', 'danger');
        event.target.checked = !event.target.checked;
    }
}

function editAutomation(event) {
    const automationId = event.target.closest('button').dataset.automationId;
    const card = document.querySelector(`[data-automation-id="${automationId}"]`);
    
    const subjectInput = card.querySelector('.automation-subject').value;
    const templateInput = card.querySelector('.automation-template').value;
    
    document.getElementById('editAutomationId').value = automationId;
    document.getElementById('editSubject').value = subjectInput;
    document.getElementById('editTemplate').value = templateInput;
}

async function testAutomation(event) {
    const automationId = event.target.closest('button').dataset.automationId;
    const recipientEmail = prompt('Enter test recipient email address:');
    
    if (!recipientEmail) return;

    try {
        const response = await apiFetch(`/api/admin/automations/${automationId}/test`, {
            method: 'POST',
            body: JSON.stringify({ recipient_email: recipientEmail })
        });

        const data = await response.json();
        if (!response.ok) {
            throw new Error(data.detail || 'Failed to send test email');
        }

        showAlert('Test email sent successfully!', 'success');
    } catch (error) {
        console.error('Error testing automation:', error);
        showAlert(error.message || 'Failed to send test email.', 'danger');
    }
}

async function viewAutomationHistory(event) {
    const automationId = event.target.closest('button').dataset.automationId;
    
    try {
        const response = await apiFetch(`/api/admin/automations/runs?automation_id=${automationId}&limit=50`);
        if (!response.ok) throw new Error('Failed to load automation runs');
        
        const runs = await response.json();
        
        const historyBody = document.getElementById('historyBody');
        if (!runs || runs.length === 0) {
            historyBody.innerHTML = '<tr><td colspan="5" class="text-center text-muted py-4">No automation runs yet.</td></tr>';
            return;
        }

        historyBody.innerHTML = runs.map(run => `
            <tr>
                <td>${new Date(run.created_at).toLocaleString()}</td>
                <td><span class="status-pill ${run.status}">${run.status}</span></td>
                <td>${escapeHtml(run.result || '')}</td>
                <td>${escapeHtml(run.error_message || '-')}</td>
            </tr>
        `).join('');
    } catch (error) {
        console.error('Error loading automation history:', error);
        showAlert('Failed to load automation history.', 'danger');
    }
}

async function saveAutomationChanges() {
    const automationId = document.getElementById('editAutomationId').value;
    const subject = document.getElementById('editSubject').value.trim();
    const template = document.getElementById('editTemplate').value.trim();

    if (!subject || !template) {
        showAlert('Subject and template cannot be empty.', 'danger');
        return;
    }

    try {
        const response = await apiFetch(`/api/admin/automations/${automationId}`, {
            method: 'PUT',
            body: JSON.stringify({
                is_active: document.querySelector(`[data-automation-id="${automationId}"] .automation-toggle`).checked,
                email_subject: subject,
                email_template: template
            })
        });

        if (!response.ok) throw new Error('Failed to save automation changes');

        showAlert('Automation updated successfully!', 'success');
        bootstrap.Modal.getInstance(document.getElementById('automationModal')).hide();
        await loadAutomations();
    } catch (error) {
        console.error('Error saving automation:', error);
        showAlert('Failed to save changes.', 'danger');
    }
}
