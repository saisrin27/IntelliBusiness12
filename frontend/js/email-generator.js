const API_BASE_URL = 'http://127.0.0.1:8000';

let selectedTone = 'Professional';
let selectedLength = 'Medium';
let activeEmailId = null;
let currentUserName = 'User';
let isGenerating = false;
let isSending = false;

document.addEventListener('DOMContentLoaded', () => {
    checkAuth();
    loadUserProfile();
    bindEvents();
    loadEmailHistory();
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
            currentUserName = user.full_name || 'User';
            document.getElementById('sidebarUserName').textContent = currentUserName;
            document.getElementById('sidebarUserRole').textContent = (user.role || 'User').toUpperCase();
            document.getElementById('sidebarUserAvatar').textContent = currentUserName.charAt(0).toUpperCase();
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

    // Tone Pills
    const tonePills = document.querySelectorAll('#tonePills .pill-option');
    tonePills.forEach((pill) => {
        pill.addEventListener('click', () => {
            tonePills.forEach((p) => p.classList.remove('active'));
            pill.classList.add('active');
            selectedTone = pill.dataset.value;
        });
    });

    // Length Pills
    const lengthPills = document.querySelectorAll('#lengthPills .pill-option');
    lengthPills.forEach((pill) => {
        pill.addEventListener('click', () => {
            lengthPills.forEach((p) => p.classList.remove('active'));
            pill.classList.add('active');
            selectedLength = pill.dataset.value;
        });
    });

    // Form Submit
    const emailForm = document.getElementById('emailForm');
    if (emailForm) {
        emailForm.addEventListener('submit', (e) => {
            e.preventDefault();
            generateEmail();
        });
    }

    // Clear Inputs
    const btnClearForm = document.getElementById('btnClearForm');
    if (btnClearForm) {
        btnClearForm.addEventListener('click', clearForm);
    }

    const btnNewEmailTop = document.getElementById('btnNewEmailTop');
    if (btnNewEmailTop) {
        btnNewEmailTop.addEventListener('click', clearForm);
    }

    // AI Refinements
    const aiImproveBar = document.getElementById('aiImproveBar');
    if (aiImproveBar) {
        aiImproveBar.addEventListener('click', (e) => {
            const btn = e.target.closest('.btn-ai-improve');
            if (btn) {
                const action = btn.dataset.action;
                if (action) improveEmail(action);
            }
        });
    }

    // Regenerate
    const btnRegenerate = document.getElementById('btnRegenerate');
    if (btnRegenerate) {
        btnRegenerate.addEventListener('click', generateEmail);
    }

    // Copy to Clipboard
    const btnCopy = document.getElementById('btnCopy');
    if (btnCopy) {
        btnCopy.addEventListener('click', copyToClipboard);
    }

    // Save Draft
    const btnSaveDraft = document.getElementById('btnSaveDraft');
    if (btnSaveDraft) {
        btnSaveDraft.addEventListener('click', saveDraft);
    }

    // Trigger Send Email Modal
    const btnSendEmailTrigger = document.getElementById('btnSendEmailTrigger');
    if (btnSendEmailTrigger) {
        btnSendEmailTrigger.addEventListener('click', openSendConfirmModal);
    }

    // Confirm Send Email
    const btnConfirmSend = document.getElementById('btnConfirmSend');
    if (btnConfirmSend) {
        btnConfirmSend.addEventListener('click', confirmSendEmail);
    }

    // Refresh History
    const btnRefreshHistory = document.getElementById('btnRefreshHistory');
    if (btnRefreshHistory) {
        btnRefreshHistory.addEventListener('click', loadEmailHistory);
    }
}

async function generateEmail() {
    const purpose = document.getElementById('emailPurpose').value.trim();
    if (!purpose) {
        alert('Please enter an email purpose or description.');
        return;
    }

    const token = localStorage.getItem('access_token');
    const btnGenerate = document.getElementById('btnGenerate');

    if (btnGenerate) {
        btnGenerate.disabled = true;
        btnGenerate.innerHTML = '<span class="spinner-border spinner-border-sm me-1" role="status"></span> Generating...';
    }

    try {
        const recipientName = document.getElementById('recipientName').value.trim();
        const recipientEmail = document.getElementById('recipientEmail').value.trim();

        const response = await fetch(`${API_BASE_URL}/api/emails/generate`, {
            method: 'POST',
            headers: {
                'Authorization': `Bearer ${token}`,
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                recipient_name: recipientName,
                recipient_email: recipientEmail,
                purpose: purpose,
                tone: selectedTone,
                length: selectedLength
            })
        });

        const data = await response.json();
        if (!response.ok) {
            throw new Error(data.detail || 'Unable to generate email.');
        }

        document.getElementById('emailSubject').value = data.subject || '';
        document.getElementById('emailContent').value = data.content || '';
        document.getElementById('editorStatusBadge').textContent = 'Draft';
        document.getElementById('editorStatusBadge').className = 'badge bg-warning-subtle text-warning border px-2 py-1';
    } catch (error) {
        alert(error.message || 'Error generating email.');
    } finally {
        if (btnGenerate) {
            btnGenerate.disabled = false;
            btnGenerate.innerHTML = '<i class="fas fa-wand-magic-sparkles me-1"></i> Generate Email';
        }
    }
}

async function improveEmail(action) {
    const subject = document.getElementById('emailSubject').value.trim();
    const content = document.getElementById('emailContent').value.trim();

    if (!content) {
        alert('Please generate or enter email content first before applying AI improvements.');
        return;
    }

    const token = localStorage.getItem('access_token');
    const aiImproveBar = document.getElementById('aiImproveBar');

    try {
        if (aiImproveBar) aiImproveBar.style.pointerEvents = 'none';

        const response = await fetch(`${API_BASE_URL}/api/emails/improve`, {
            method: 'POST',
            headers: {
                'Authorization': `Bearer ${token}`,
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                subject: subject,
                content: content,
                action: action
            })
        });

        const data = await response.json();
        if (!response.ok) {
            throw new Error(data.detail || 'Unable to refine email.');
        }

        if (data.subject) document.getElementById('emailSubject').value = data.subject;
        if (data.content) document.getElementById('emailContent').value = data.content;
    } catch (error) {
        alert(error.message || 'Error refining email.');
    } finally {
        if (aiImproveBar) aiImproveBar.style.pointerEvents = 'auto';
    }
}

async function saveDraft() {
    const recipientEmail = document.getElementById('recipientEmail').value.trim();
    const subject = document.getElementById('emailSubject').value.trim();
    const content = document.getElementById('emailContent').value.trim();

    if (!recipientEmail || !recipientEmail.includes('@')) {
        alert('Please enter a valid recipient email address.');
        return;
    }
    if (!subject) {
        alert('Please enter a subject line.');
        return;
    }
    if (!content) {
        alert('Email content cannot be empty.');
        return;
    }

    const token = localStorage.getItem('access_token');
    const btnSaveDraft = document.getElementById('btnSaveDraft');

    if (btnSaveDraft) {
        btnSaveDraft.disabled = true;
        btnSaveDraft.innerHTML = '<span class="spinner-border spinner-border-sm me-1"></span> Saving...';
    }

    try {
        const recipientName = document.getElementById('recipientName').value.trim();

        const response = await fetch(`${API_BASE_URL}/api/emails/draft`, {
            method: 'POST',
            headers: {
                'Authorization': `Bearer ${token}`,
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                id: activeEmailId,
                recipient_name: recipientName,
                recipient_email: recipientEmail,
                subject: subject,
                content: content,
                tone: selectedTone,
                length: selectedLength
            })
        });

        const data = await response.json();
        if (!response.ok) {
            throw new Error(data.detail || 'Unable to save draft.');
        }

        activeEmailId = data.id;
        document.getElementById('editorStatusBadge').textContent = 'Draft Saved';
        document.getElementById('editorStatusBadge').className = 'badge bg-warning-subtle text-warning border px-2 py-1';
        
        loadEmailHistory();
    } catch (error) {
        alert(error.message || 'Error saving draft.');
    } finally {
        if (btnSaveDraft) {
            btnSaveDraft.disabled = false;
            btnSaveDraft.innerHTML = '<i class="fas fa-bookmark me-1"></i> Save Draft';
        }
    }
}

function openSendConfirmModal() {
    const recipientEmail = document.getElementById('recipientEmail').value.trim();
    const subject = document.getElementById('emailSubject').value.trim();
    const content = document.getElementById('emailContent').value.trim();
    const recipientName = document.getElementById('recipientName').value.trim();

    if (!recipientEmail || !recipientEmail.includes('@') || !recipientEmail.includes('.')) {
        alert('Please enter a valid recipient email address.');
        return;
    }
    if (!subject) {
        alert('Please enter an email subject line.');
        return;
    }
    if (!content) {
        alert('Email content cannot be empty.');
        return;
    }

    const modalSenderText = document.getElementById('modalSenderText');
    const modalRecipientText = document.getElementById('modalRecipientText');
    const modalSubjectText = document.getElementById('modalSubjectText');
    const modalContentPreview = document.getElementById('modalContentPreview');

    if (modalSenderText) {
        modalSenderText.textContent = `Regards, ${currentUserName}`;
    }
    if (modalRecipientText) {
        modalRecipientText.textContent = recipientName ? `${recipientName} <${recipientEmail}>` : recipientEmail;
    }
    if (modalSubjectText) {
        modalSubjectText.textContent = subject;
    }
    if (modalContentPreview) {
        modalContentPreview.textContent = content;
    }

    const modalEl = document.getElementById('sendConfirmModal');
    if (modalEl) {
        const modal = new bootstrap.Modal(modalEl);
        modal.show();
    }
}

async function confirmSendEmail() {
    if (isSending) return;

    const token = localStorage.getItem('access_token');
    const recipientEmail = document.getElementById('recipientEmail').value.trim();
    const recipientName = document.getElementById('recipientName').value.trim();
    const subject = document.getElementById('emailSubject').value.trim();
    const content = document.getElementById('emailContent').value.trim();

    const btnConfirmSend = document.getElementById('btnConfirmSend');
    if (btnConfirmSend) {
        btnConfirmSend.disabled = true;
        btnConfirmSend.innerHTML = '<span class="spinner-border spinner-border-sm me-1" role="status"></span> Sending Email...';
    }

    isSending = true;

    try {
        const response = await fetch(`${API_BASE_URL}/api/emails/send`, {
            method: 'POST',
            headers: {
                'Authorization': `Bearer ${token}`,
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                id: activeEmailId,
                recipient_name: recipientName,
                recipient_email: recipientEmail,
                subject: subject,
                content: content
            })
        });

        const data = await response.json();
        if (!response.ok) {
            throw new Error(data.detail || 'Email sending failed.');
        }

        activeEmailId = data.id;

        // Hide Modal
        const modalEl = document.getElementById('sendConfirmModal');
        const modal = bootstrap.Modal.getInstance(modalEl);
        if (modal) modal.hide();

        alert('🎉 Email sent successfully!');
        document.getElementById('editorStatusBadge').textContent = 'Sent';
        document.getElementById('editorStatusBadge').className = 'badge bg-success-subtle text-success border px-2 py-1';
        
        loadEmailHistory();
    } catch (error) {
        // Hide Modal
        const modalEl = document.getElementById('sendConfirmModal');
        const modal = bootstrap.Modal.getInstance(modalEl);
        if (modal) modal.hide();

        alert(`Email Sending Error: ${error.message}`);
        document.getElementById('editorStatusBadge').textContent = 'Failed';
        document.getElementById('editorStatusBadge').className = 'badge bg-danger-subtle text-danger border px-2 py-1';
        
        loadEmailHistory();
    } finally {
        isSending = false;
        if (btnConfirmSend) {
            btnConfirmSend.disabled = false;
            btnConfirmSend.innerHTML = '<i class="fas fa-paper-plane me-1"></i> Confirm & Send Email';
        }
    }
}

async function loadEmailHistory() {
    const token = localStorage.getItem('access_token');
    const listEl = document.getElementById('emailHistoryList');
    if (!listEl) return;

    try {
        const response = await fetch(`${API_BASE_URL}/api/emails`, {
            headers: {
                'Authorization': `Bearer ${token}`,
                'Content-Type': 'application/json'
            }
        });

        if (!response.ok) throw new Error('Unable to load email history.');
        const emails = await response.json();

        renderEmailHistory(emails);
    } catch (error) {
        console.error(error);
    }
}

function renderEmailHistory(emails) {
    const listEl = document.getElementById('emailHistoryList');
    if (!listEl) return;

    if (!Array.isArray(emails) || emails.length === 0) {
        listEl.innerHTML = '<div class="text-muted small px-2 py-4 text-center">No email history found.</div>';
        return;
    }

    listEl.innerHTML = emails.map((item) => {
        const isActive = activeEmailId === item.id ? 'active' : '';
        const subject = escapeHtml(item.subject || 'No Subject');
        const recipient = escapeHtml(item.recipient_email || 'No Recipient');
        const status = item.status || 'draft';

        let badgeClass = 'badge-status-draft';
        if (status === 'sent') badgeClass = 'badge-status-sent';
        else if (status === 'failed') badgeClass = 'badge-status-failed';
        else if (status === 'sending') badgeClass = 'badge-status-sending';

        return `
            <div class="email-history-item ${isActive}" data-id="${item.id}">
                <div class="d-flex align-items-center justify-content-between mb-1">
                    <span class="badge ${badgeClass} px-2 py-1 rounded-pill text-capitalize small">${status}</span>
                    <button class="btn btn-sm text-danger btn-delete-email p-0" data-id="${item.id}" title="Delete">
                        <i class="fas fa-trash-alt"></i>
                    </button>
                </div>
                <div class="fw-semibold text-dark text-truncate mb-1" style="font-size: 0.88rem;">${subject}</div>
                <div class="text-muted small text-truncate"><i class="fas fa-user me-1"></i> ${recipient}</div>
            </div>
        `;
    }).join('');

    listEl.querySelectorAll('.email-history-item').forEach((item) => {
        item.addEventListener('click', (e) => {
            if (e.target.closest('.btn-delete-email')) return;
            const id = Number(item.dataset.id);
            if (id) reopenEmail(id);
        });
    });

    listEl.querySelectorAll('.btn-delete-email').forEach((btn) => {
        btn.addEventListener('click', async (e) => {
            e.stopPropagation();
            const id = Number(btn.dataset.id);
            if (id) await deleteEmail(id);
        });
    });
}

async function reopenEmail(id) {
    const token = localStorage.getItem('access_token');
    try {
        const response = await fetch(`${API_BASE_URL}/api/emails/${id}`, {
            headers: {
                'Authorization': `Bearer ${token}`,
                'Content-Type': 'application/json'
            }
        });

        if (!response.ok) throw new Error('Unable to open email details.');
        const email = await response.json();

        activeEmailId = email.id;
        document.getElementById('recipientName').value = email.recipient_name || '';
        document.getElementById('recipientEmail').value = email.recipient_email || '';
        document.getElementById('emailSubject').value = email.subject || '';
        document.getElementById('emailContent').value = email.content || '';

        const status = email.status || 'draft';
        const badge = document.getElementById('editorStatusBadge');
        badge.textContent = status.toUpperCase();
        if (status === 'sent') badge.className = 'badge bg-success-subtle text-success border px-2 py-1';
        else if (status === 'failed') badge.className = 'badge bg-danger-subtle text-danger border px-2 py-1';
        else badge.className = 'badge bg-warning-subtle text-warning border px-2 py-1';

        loadEmailHistory();
    } catch (error) {
        alert(error.message || 'Unable to load email details.');
    }
}

async function deleteEmail(id) {
    if (!confirm('Delete this email record from history?')) return;

    const token = localStorage.getItem('access_token');
    try {
        const response = await fetch(`${API_BASE_URL}/api/emails/${id}`, {
            method: 'DELETE',
            headers: {
                'Authorization': `Bearer ${token}`,
                'Content-Type': 'application/json'
            }
        });

        if (!response.ok) throw new Error('Unable to delete email record.');

        if (activeEmailId === id) clearForm();
        else loadEmailHistory();
    } catch (error) {
        alert(error.message || 'Unable to delete email record.');
    }
}

function copyToClipboard() {
    const subject = document.getElementById('emailSubject').value.trim();
    const content = document.getElementById('emailContent').value.trim();

    if (!content) {
        alert('Nothing to copy.');
        return;
    }

    const fullText = `Subject: ${subject}\n\n${content}`;
    navigator.clipboard.writeText(fullText).then(() => {
        alert('Email copied to clipboard!');
    }).catch(() => {
        alert('Failed to copy to clipboard.');
    });
}

function clearForm() {
    activeEmailId = null;
    document.getElementById('recipientName').value = '';
    document.getElementById('recipientEmail').value = '';
    document.getElementById('emailPurpose').value = '';
    document.getElementById('emailSubject').value = '';
    document.getElementById('emailContent').value = '';
    
    document.getElementById('editorStatusBadge').textContent = 'Draft';
    document.getElementById('editorStatusBadge').className = 'badge bg-light text-muted border px-2 py-1';

    loadEmailHistory();
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
