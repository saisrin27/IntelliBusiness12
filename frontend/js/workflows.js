const API_BASE_URL = "https://intellibusiness-db.onrender.com";

let workflowActionSteps = [];

document.addEventListener('DOMContentLoaded', () => {
    checkAuth();
    loadUserProfile();
    bindEvents();
    loadWorkflows();
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

    const btnCreateWorkflowTop = document.getElementById('btnCreateWorkflowTop');
    if (btnCreateWorkflowTop) {
        btnCreateWorkflowTop.addEventListener('click', () => openWorkflowModal());
    }

    const btnRefreshWorkflows = document.getElementById('btnRefreshWorkflows');
    if (btnRefreshWorkflows) {
        btnRefreshWorkflows.addEventListener('click', loadWorkflows);
    }

    const btnViewHistoryTop = document.getElementById('btnViewHistoryTop');
    if (btnViewHistoryTop) {
        btnViewHistoryTop.addEventListener('click', openHistoryModal);
    }

    const btnAddActionStep = document.getElementById('btnAddActionStep');
    if (btnAddActionStep) {
        btnAddActionStep.addEventListener('click', () => addActionStep());
    }

    const btnSaveWorkflow = document.getElementById('btnSaveWorkflow');
    if (btnSaveWorkflow) {
        btnSaveWorkflow.addEventListener('click', saveWorkflow);
    }

    const btnBuildWithAi = document.getElementById('btnBuildWithAi');
    if (btnBuildWithAi) {
        btnBuildWithAi.addEventListener('click', generateWorkflowWithAi);
    }

    document.querySelectorAll('.pill-ai-wf').forEach((pill) => {
        pill.addEventListener('click', () => {
            const prompt = pill.dataset.prompt;
            document.getElementById('aiWorkflowPromptInput').value = prompt;
            generateWorkflowWithAi();
        });
    });
}

async function generateWorkflowWithAi() {
    const inputEl = document.getElementById('aiWorkflowPromptInput');
    const prompt = inputEl ? inputEl.value.trim() : '';

    if (!prompt) {
        alert('Please describe your workflow in simple language.');
        return;
    }

    const token = localStorage.getItem('access_token');
    const btn = document.getElementById('btnBuildWithAi');
    if (btn) {
        btn.disabled = true;
        btn.innerHTML = '<span class="spinner-border spinner-border-sm me-1"></span> AI Generating...';
    }

    try {
        const response = await fetch(`${API_BASE_URL}/api/workflows/generate-from-ai`, {
            method: 'POST',
            headers: {
                'Authorization': `Bearer ${token}`,
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ prompt: prompt })
        });

        const data = await response.json();
        if (!response.ok) throw new Error(data.detail || 'Unable to generate workflow.');

        // Open modal with preview of generated workflow
        openWorkflowModal(data);
    } catch (error) {
        alert(error.message || 'Error generating workflow with AI.');
    } finally {
        if (btn) {
            btn.disabled = false;
            btn.innerHTML = '<i class="fas fa-robot me-1"></i> Build Workflow';
        }
    }
}


async function loadWorkflows() {
    const token = localStorage.getItem('access_token');
    const container = document.getElementById('workflowsGrid');
    if (!container) return;

    container.innerHTML = '<div class="col-12 text-center py-5 text-muted"><span class="spinner-border spinner-border-sm me-2"></span> Loading workflows...</div>';

    try {
        const response = await fetch(`${API_BASE_URL}/api/workflows`, {
            headers: {
                'Authorization': `Bearer ${token}`,
                'Content-Type': 'application/json'
            }
        });

        if (!response.ok) throw new Error('Unable to fetch workflows.');
        const workflows = await response.json();

        renderWorkflowsGrid(container, workflows);
    } catch (error) {
        container.innerHTML = `<div class="col-12 text-center py-5 text-danger">${escapeHtml(error.message)}</div>`;
    }
}

function renderWorkflowsGrid(container, workflows) {
    if (!Array.isArray(workflows) || workflows.length === 0) {
        container.innerHTML = `
            <div class="col-12 text-center py-5">
                <div class="mb-3 text-muted fs-1"><i class="fas fa-network-wired"></i></div>
                <h5 class="fw-bold text-dark mb-1">No Workflows Created Yet</h5>
                <p class="text-muted small mb-3">Automate multi-step business routines like document analysis & email alerts.</p>
                <button class="btn btn-primary rounded-pill px-4 fw-semibold" onclick="openWorkflowModal()">
                    <i class="fas fa-plus me-1"></i> Create First Workflow
                </button>
            </div>
        `;
        return;
    }

    container.innerHTML = workflows.map((wf) => {
        const triggerLabel = getTriggerLabel(wf.trigger_type);
        const actions = Array.isArray(wf.actions) ? wf.actions : [];
        const isActiveChecked = wf.is_active ? 'checked' : '';
        const activeBadge = wf.is_active 
            ? '<span class="badge bg-success-subtle text-success px-2 py-1"><i class="fas fa-check-circle me-1"></i> Active</span>' 
            : '<span class="badge bg-secondary-subtle text-secondary px-2 py-1"><i class="fas fa-pause-circle me-1"></i> Disabled</span>';

        const actionPills = actions.map((a, idx) => `
            <span class="action-pill mb-1 me-1">
                <i class="${getActionIcon(a.action_type)} text-purple"></i> ${idx + 1}. ${getActionLabel(a.action_type)}
            </span>
        `).join('');

        return `
            <div class="col-md-6 col-lg-4">
                <div class="workflow-card h-100 p-4 d-flex flex-column justify-content-between">
                    <div>
                        <div class="d-flex align-items-center justify-content-between mb-2">
                            <span class="badge badge-trigger rounded-pill px-2 py-1 small">${triggerLabel}</span>
                            ${activeBadge}
                        </div>
                        
                        <h6 class="fw-bold text-dark mb-2">${escapeHtml(wf.name)}</h6>
                        
                        <div class="mb-3">
                            <div class="text-muted small fw-semibold mb-1">Actions Chain (${actions.length} steps):</div>
                            <div>${actionPills || '<span class="text-muted small">No steps</span>'}</div>
                        </div>
                    </div>

                    <div class="border-top pt-3 mt-2 d-flex align-items-center justify-content-between">
                        <div class="form-check form-switch m-0" title="Toggle active status">
                            <input class="form-check-input btn-toggle-wf" type="checkbox" data-id="${wf.id}" ${isActiveChecked}>
                        </div>
                        <div class="d-flex align-items-center gap-2">
                            <button class="btn btn-sm btn-outline-primary rounded-pill btn-run-wf" data-id="${wf.id}" title="Run Now">
                                <i class="fas fa-play me-1"></i> Run Now
                            </button>
                            <button class="btn btn-sm btn-light text-muted border rounded-circle btn-edit-wf" data-id="${wf.id}" title="Edit">
                                <i class="fas fa-edit"></i>
                            </button>
                            <button class="btn btn-sm btn-light text-danger border rounded-circle btn-delete-wf" data-id="${wf.id}" title="Delete">
                                <i class="fas fa-trash-alt"></i>
                            </button>
                        </div>
                    </div>
                </div>
            </div>
        `;
    }).join('');

    // Bind item buttons
    container.querySelectorAll('.btn-toggle-wf').forEach((sw) => {
        sw.addEventListener('change', async () => {
            const id = Number(sw.dataset.id);
            if (id) await toggleWorkflow(id);
        });
    });

    container.querySelectorAll('.btn-run-wf').forEach((btn) => {
        btn.addEventListener('click', async () => {
            const id = Number(btn.dataset.id);
            if (id) await runWorkflow(id);
        });
    });

    container.querySelectorAll('.btn-edit-wf').forEach((btn) => {
        btn.addEventListener('click', async () => {
            const id = Number(btn.dataset.id);
            if (id) await editWorkflow(id);
        });
    });

    container.querySelectorAll('.btn-delete-wf').forEach((btn) => {
        btn.addEventListener('click', async () => {
            const id = Number(btn.dataset.id);
            if (id) await deleteWorkflow(id);
        });
    });
}

function openWorkflowModal(existingWf = null) {
    const editIdEl = document.getElementById('workflowEditId');
    const nameEl = document.getElementById('workflowName');
    const triggerEl = document.getElementById('triggerTypeSelect');
    const activeEl = document.getElementById('workflowIsActive');
    const modalTitleEl = document.getElementById('workflowModalLabel');

    if (existingWf && existingWf.id) {
        editIdEl.value = existingWf.id;
        nameEl.value = existingWf.name || '';
        triggerEl.value = existingWf.trigger_type || 'document_uploaded';
        activeEl.checked = !!existingWf.is_active;
        modalTitleEl.innerHTML = '<i class="fas fa-edit text-primary me-2"></i> Edit Workflow';
        workflowActionSteps = Array.isArray(existingWf.actions) ? JSON.parse(JSON.stringify(existingWf.actions)) : [];
    } else if (existingWf) {
        // AI Generated Draft Workflow (no id)
        editIdEl.value = '';
        nameEl.value = existingWf.name || '';
        triggerEl.value = existingWf.trigger_type || 'document_uploaded';
        activeEl.checked = true;
        modalTitleEl.innerHTML = '<i class="fas fa-wand-magic-sparkles text-primary me-2"></i> Review AI-Generated Workflow';
        workflowActionSteps = Array.isArray(existingWf.actions) ? JSON.parse(JSON.stringify(existingWf.actions)) : [];
    } else {
        editIdEl.value = '';
        nameEl.value = '';
        triggerEl.value = 'document_uploaded';
        activeEl.checked = true;
        modalTitleEl.innerHTML = '<i class="fas fa-network-wired text-primary me-2"></i> Create New Workflow';
        workflowActionSteps = [
            { action_type: 'generate_summary', config: {} },
            { action_type: 'send_email', config: {} }
        ];
    }

    renderActionStepsBuilder();

    const modalEl = document.getElementById('workflowModal');
    if (modalEl) {
        const modal = new bootstrap.Modal(modalEl);
        modal.show();
    }
}

function addActionStep() {
    workflowActionSteps.push({ action_type: 'generate_summary', config: {} });
    renderActionStepsBuilder();
}

function removeActionStep(idx) {
    if (workflowActionSteps.length <= 1) {
        alert('A workflow must contain at least one action step.');
        return;
    }
    workflowActionSteps.splice(idx, 1);
    renderActionStepsBuilder();
}

function renderActionStepsBuilder() {
    const container = document.getElementById('actionStepsContainer');
    if (!container) return;

    if (workflowActionSteps.length === 0) {
        workflowActionSteps.push({ action_type: 'generate_summary', config: {} });
    }

    let html = '';
    workflowActionSteps.forEach((step, idx) => {
        html += `
            ${idx > 0 ? '<div class="flow-arrow"><i class="fas fa-arrow-down"></i></div>' : ''}
            <div class="builder-node builder-action mb-2" data-step-idx="${idx}">
                <div class="d-flex align-items-center justify-content-between mb-2">
                    <div class="node-badge">STEP ${idx + 1}. ACTION</div>
                    ${workflowActionSteps.length > 1 ? `<button type="button" class="btn btn-sm btn-link text-danger p-0 btn-remove-step" data-step-idx="${idx}"><i class="fas fa-trash-alt"></i></button>` : ''}
                </div>
                <div class="row g-2">
                    <div class="col-12">
                        <select class="form-select form-select-sm rounded-3 step-type-select" data-step-idx="${idx}">
                            <option value="generate_summary" ${step.action_type === 'generate_summary' ? 'selected' : ''}>🤖 Generate AI Summary</option>
                            <option value="send_email" ${step.action_type === 'send_email' ? 'selected' : ''}>✉️ Send Email Alert</option>
                            <option value="generate_notification" ${step.action_type === 'generate_notification' ? 'selected' : ''}>🔔 Generate Notification Log</option>
                            <option value="run_analysis" ${step.action_type === 'run_analysis' ? 'selected' : ''}>📊 Run Strategic AI Analysis</option>
                        </select>
                    </div>
                </div>
            </div>
        `;
    });

    container.innerHTML = html;

    // Bind selects & remove buttons
    container.querySelectorAll('.step-type-select').forEach((sel) => {
        sel.addEventListener('change', (e) => {
            const idx = Number(sel.dataset.stepIdx);
            workflowActionSteps[idx].action_type = e.target.value;
        });
    });

    container.querySelectorAll('.btn-remove-step').forEach((btn) => {
        btn.addEventListener('click', () => {
            const idx = Number(btn.dataset.stepIdx);
            removeActionStep(idx);
        });
    });
}

async function saveWorkflow(runImmediately = false) {
    const name = document.getElementById('workflowName').value.trim();
    const trigger_type = document.getElementById('triggerTypeSelect').value;
    const is_active = document.getElementById('workflowIsActive').checked;
    const rawEditId = document.getElementById('workflowEditId').value;
    
    // Ensure editId is a valid numeric ID, or null
    const editId = (rawEditId && rawEditId !== 'undefined' && rawEditId !== 'null' && !isNaN(Number(rawEditId))) ? Number(rawEditId) : null;

    if (!name) {
        alert('Please enter a workflow name.');
        return;
    }

    if (!Array.isArray(workflowActionSteps) || workflowActionSteps.length === 0) {
        alert('Please add at least one action step.');
        return;
    }

    const token = localStorage.getItem('access_token');
    const btnSave = document.getElementById('btnSaveWorkflow');
    const btnSaveRun = document.getElementById('btnSaveAndRunWorkflow');
    
    if (btnSave) btnSave.disabled = true;
    if (btnSaveRun) {
        btnSaveRun.disabled = true;
        if (runImmediately) btnSaveRun.innerHTML = '<span class="spinner-border spinner-border-sm me-1"></span> Saving & Running...';
    }

    try {
        const payload = {
            name: name,
            trigger_type: trigger_type,
            actions: workflowActionSteps,
            is_active: is_active
        };

        const url = editId ? `${API_BASE_URL}/api/workflows/${editId}` : `${API_BASE_URL}/api/workflows`;
        const method = editId ? 'PUT' : 'POST';

        const response = await fetch(url, {
            method: method,
            headers: {
                'Authorization': `Bearer ${token}`,
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(payload)
        });

        const data = await response.json();
        if (!response.ok) {
            let errorMsg = 'Unable to save workflow.';
            if (data && data.detail) {
                if (typeof data.detail === 'string') {
                    errorMsg = data.detail;
                } else if (Array.isArray(data.detail)) {
                    errorMsg = data.detail.map(e => `${e.loc ? e.loc.join('.') : ''}: ${e.msg}`).join(', ');
                } else {
                    errorMsg = JSON.stringify(data.detail);
                }
            }
            throw new Error(errorMsg);
        }

        // Hide Modal
        const modalEl = document.getElementById('workflowModal');
        const modal = bootstrap.Modal.getInstance(modalEl);
        if (modal) modal.hide();

        await loadWorkflows();

        if (runImmediately && data.id) {
            await runWorkflow(data.id);
        }
    } catch (error) {
        const msg = error.message || (typeof error === 'object' ? JSON.stringify(error) : String(error));
        alert(`Save Error: ${msg}`);
    } finally {
        if (btnSave) btnSave.disabled = false;
        if (btnSaveRun) {
            btnSaveRun.disabled = false;
            btnSaveRun.innerHTML = '<i class="fas fa-play me-1"></i> Save & Run Workflow';
        }
    }
}

async function toggleWorkflow(id) {
    const token = localStorage.getItem('access_token');
    try {
        const response = await fetch(`${API_BASE_URL}/api/workflows/${id}/toggle`, {
            method: 'POST',
            headers: {
                'Authorization': `Bearer ${token}`,
                'Content-Type': 'application/json'
            }
        });
        if (!response.ok) throw new Error('Unable to toggle workflow status.');
        loadWorkflows();
    } catch (error) {
        alert(error.message);
    }
}

async function runWorkflow(id) {
    const token = localStorage.getItem('access_token');
    try {
        const response = await fetch(`${API_BASE_URL}/api/workflows/${id}/run`, {
            method: 'POST',
            headers: {
                'Authorization': `Bearer ${token}`,
                'Content-Type': 'application/json'
            }
        });

        const run = await response.json();
        if (!response.ok) throw new Error(run.detail || 'Workflow execution failed.');

        alert(`🎉 Workflow executed! Status: ${run.status.toUpperCase()}`);
        openHistoryModal();
    } catch (error) {
        alert(error.message || 'Error running workflow.');
    }
}

async function editWorkflow(id) {
    const token = localStorage.getItem('access_token');
    try {
        const response = await fetch(`${API_BASE_URL}/api/workflows/${id}`, {
            headers: {
                'Authorization': `Bearer ${token}`,
                'Content-Type': 'application/json'
            }
        });

        if (!response.ok) throw new Error('Unable to fetch workflow details.');
        const wf = await response.json();

        openWorkflowModal(wf);
    } catch (error) {
        alert(error.message);
    }
}

async function deleteWorkflow(id) {
    if (!confirm('Delete this workflow?')) return;

    const token = localStorage.getItem('access_token');
    try {
        const response = await fetch(`${API_BASE_URL}/api/workflows/${id}`, {
            method: 'DELETE',
            headers: {
                'Authorization': `Bearer ${token}`,
                'Content-Type': 'application/json'
            }
        });

        if (!response.ok) throw new Error('Unable to delete workflow.');
        loadWorkflows();
    } catch (error) {
        alert(error.message);
    }
}

async function openHistoryModal() {
    const token = localStorage.getItem('access_token');
    const container = document.getElementById('historyListContainer');
    if (!container) return;

    container.innerHTML = '<div class="text-center py-4 text-muted"><span class="spinner-border spinner-border-sm me-2"></span> Loading execution history...</div>';

    const modalEl = document.getElementById('historyModal');
    if (modalEl) {
        const modal = new bootstrap.Modal(modalEl);
        modal.show();
    }

    try {
        const response = await fetch(`${API_BASE_URL}/api/workflows/runs/history`, {
            headers: {
                'Authorization': `Bearer ${token}`,
                'Content-Type': 'application/json'
            }
        });

        if (!response.ok) throw new Error('Unable to load execution history.');
        const runs = await response.json();

        renderHistoryList(container, runs);
    } catch (error) {
        container.innerHTML = `<div class="text-center py-4 text-danger">${escapeHtml(error.message)}</div>`;
    }
}

function renderHistoryList(container, runs) {
    if (!Array.isArray(runs) || runs.length === 0) {
        container.innerHTML = '<div class="text-center py-4 text-muted small">No workflow execution history found.</div>';
        return;
    }

    container.innerHTML = runs.map((run) => {
        const status = run.status || 'pending';
        let badgeClass = 'badge-run-pending';
        if (status === 'completed') badgeClass = 'badge-run-completed';
        else if (status === 'failed') badgeClass = 'badge-run-failed';
        else if (status === 'running') badgeClass = 'badge-run-running';

        const startTime = new Date(run.started_at).toLocaleString();

        return `
            <div class="border rounded-3 p-3 mb-2 bg-white">
                <div class="d-flex align-items-center justify-content-between mb-1">
                    <span class="badge ${badgeClass} px-2 py-1 rounded-pill text-capitalize small">${status}</span>
                    <small class="text-muted"><i class="far fa-clock me-1"></i> ${startTime}</small>
                </div>
                <div class="fw-semibold text-dark small mb-1">Execution Run #${run.id} (Workflow ID: ${run.workflow_id})</div>
                ${run.error_message ? `<div class="text-danger small mt-1"><i class="fas fa-exclamation-triangle me-1"></i> ${escapeHtml(run.error_message)}</div>` : ''}
            </div>
        `;
    }).join('');
}

function getTriggerLabel(type) {
    switch (type) {
        case 'document_uploaded': return '📄 Document Uploaded';
        case 'document_processed': return '✅ Document Processed';
        case 'email_generated': return '✉️ Email Generated';
        case 'manual_trigger': return '⚡ Manual Trigger';
        default: return type;
    }
}

function getActionLabel(type) {
    switch (type) {
        case 'generate_summary': return 'Generate AI Summary';
        case 'send_email': return 'Send Email Alert';
        case 'generate_notification': return 'Generate Notification';
        case 'run_analysis': return 'Run AI Analysis';
        default: return type;
    }
}

function getActionIcon(type) {
    switch (type) {
        case 'generate_summary': return 'fas fa-robot';
        case 'send_email': return 'fas fa-envelope';
        case 'generate_notification': return 'fas fa-bell';
        case 'run_analysis': return 'fas fa-chart-line';
        default: return 'fas fa-cog';
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
