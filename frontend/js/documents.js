document.addEventListener('DOMContentLoaded', () => {
    ensureAuthenticated();
    bindGlobalHandlers();
    bindUploadEvents();
    bindSearch();
    loadDocumentStats();
    loadDocuments();
});

const API_BASE_URL = 'http://127.0.0.1:8000';
const state = {
    selectedFiles: [],
    documents: [],
    currentFilters: {
        search: '',
        filter: 'all',
        sort: 'newest',
    },
};

function ensureAuthenticated() {
    const token = localStorage.getItem('access_token');
    if (!token) {
        window.location.href = 'login.html';
        return;
    }

    const user = localStorage.getItem('user');
    if (user) {
        const parsed = JSON.parse(user);
        const profileName = document.getElementById('profileModalName');
        const profileCompany = document.getElementById('profileModalCompany');
        const profileEmail = document.getElementById('profileModalEmail');
        const avatar = document.getElementById('profileModalAvatar');

        if (profileName) profileName.textContent = parsed.full_name || '-';
        if (profileCompany) profileCompany.textContent = parsed.company_name || '-';
        if (profileEmail) profileEmail.textContent = parsed.email || '-';
        if (avatar) avatar.textContent = getInitials(parsed.full_name || 'User');
    }
}

function bindGlobalHandlers() {
    document.getElementById('btnUploadDocumentHeader')?.addEventListener('click', () => {
        document.getElementById('documentFileInput')?.click();
    });

    document.getElementById('btnUploadDocumentHero')?.addEventListener('click', () => {
        document.getElementById('documentFileInput')?.click();
    });

    document.getElementById('btnBrowseFiles')?.addEventListener('click', () => {
        document.getElementById('documentFileInput')?.click();
    });

    document.getElementById('btnLogoutSidebar')?.addEventListener('click', logoutUser);
    document.getElementById('btnLogoutTopbar')?.addEventListener('click', logoutUser);
}

function bindUploadEvents() {
    const dropzone = document.getElementById('uploadDropzone');
    const fileInput = document.getElementById('documentFileInput');

    dropzone?.addEventListener('dragover', (event) => {
        event.preventDefault();
        dropzone.classList.add('active');
    });

    dropzone?.addEventListener('dragleave', () => dropzone.classList.remove('active'));
    dropzone?.addEventListener('drop', (event) => {
        event.preventDefault();
        dropzone.classList.remove('active');
        const files = Array.from(event.dataTransfer.files || []);
        enqueueFiles(files);
    });

    fileInput?.addEventListener('change', (event) => {
        const files = Array.from(event.target.files || []);
        enqueueFiles(files);
        fileInput.value = '';
    });

    dropzone?.addEventListener('click', () => fileInput?.click());
}

function bindSearch() {
    const searchInput = document.getElementById('documentsSearchInput');
    const topSearchInput = document.getElementById('documentSearchInput');
    const filterSelect = document.getElementById('documentsFilterSelect');
    const sortSelect = document.getElementById('documentsSortSelect');

    searchInput?.addEventListener('input', (event) => {
        state.currentFilters.search = event.target.value.trim();
        loadDocuments();
    });

    topSearchInput?.addEventListener('input', (event) => {
        state.currentFilters.search = event.target.value.trim();
        document.getElementById('documentsSearchInput').value = event.target.value;
        loadDocuments();
    });

    filterSelect?.addEventListener('change', (event) => {
        state.currentFilters.filter = event.target.value;
        loadDocuments();
    });

    sortSelect?.addEventListener('change', (event) => {
        state.currentFilters.sort = event.target.value;
        loadDocuments();
    });
}

function enqueueFiles(files) {
    const valid = [];
    const errors = [];

    for (const file of files) {
        const extension = `.${file.name.split('.').pop().toLowerCase()}`;
        const allowed = ['.pdf', '.docx', '.pptx', '.xlsx', '.txt'];
        if (!allowed.includes(extension)) {
            errors.push(`${file.name}: unsupported file type.`);
            continue;
        }
        if (file.size > 10 * 1024 * 1024) {
            errors.push(`${file.name}: file is larger than 10 MB.`);
            continue;
        }
        valid.push(file);
    }

    if (errors.length) {
        showToast(errors.join('\n'));
    }

    if (!valid.length) return;

    state.selectedFiles = [...state.selectedFiles, ...valid];
    renderSelectedFiles();
    uploadDocuments();
}

function renderSelectedFiles() {
    const container = document.getElementById('selectedFilesContainer');
    if (!container) return;

    if (!state.selectedFiles.length) {
        container.innerHTML = '';
        return;
    }

    container.innerHTML = state.selectedFiles.map((file, index) => `
        <div class="selected-file-item">
            <div class="selected-file-meta">
                <div class="selected-file-icon"><i class="fas fa-file-alt"></i></div>
                <div>
                    <div class="file-name">${escapeHtml(file.name)}</div>
                    <div class="file-meta">${file.type || 'Unknown'} • ${formatFileSize(file.size)}</div>
                </div>
            </div>
            <button type="button" class="remove-file-btn" data-index="${index}" aria-label="Remove file">
                <i class="fas fa-times"></i>
            </button>
        </div>
    `).join('');

    container.querySelectorAll('.remove-file-btn').forEach((button) => {
        button.addEventListener('click', () => {
            const index = Number(button.dataset.index);
            state.selectedFiles.splice(index, 1);
            renderSelectedFiles();
        });
    });
}

async function uploadDocuments() {
    if (!state.selectedFiles.length) return;

    const token = localStorage.getItem('access_token');
    const formData = new FormData();
    state.selectedFiles.forEach((file) => formData.append('files', file));

    try {
        const response = await fetch(`${API_BASE_URL}/api/documents/upload`, {
            method: 'POST',
            headers: {
                'Authorization': `Bearer ${token}`
            },
            body: formData
        });

        const data = await response.json().catch(() => ({}));
        if (!response.ok) {
            throw new Error(data.detail || 'Upload failed.');
        }

        state.selectedFiles = [];
        renderSelectedFiles();
        showToast('Document uploaded successfully.');
        loadDocumentStats();
        loadDocuments();
    } catch (error) {
        console.error(error);
        showToast(error.message || 'Upload failed.');
    }
}

async function loadDocumentStats() {
    const token = localStorage.getItem('access_token');
    try {
        const response = await fetch(`${API_BASE_URL}/api/documents/stats`, {
            headers: {
                'Authorization': `Bearer ${token}`,
                'Content-Type': 'application/json'
            }
        });
        if (!response.ok) throw new Error('Unable to get stats');
        const data = await response.json();
        document.getElementById('totalDocumentsStat').textContent = data.total || 0;
        document.getElementById('processingDocumentsStat').textContent = data.processing || 0;
        document.getElementById('completedDocumentsStat').textContent = data.completed || 0;
        document.getElementById('failedDocumentsStat').textContent = data.failed || 0;
    } catch (error) {
        console.error(error);
    }
}

async function loadDocuments() {
    const token = localStorage.getItem('access_token');
    const search = state.currentFilters.search;
    const filter = state.currentFilters.filter;
    const sort = state.currentFilters.sort;

    try {
        const url = new URL(`${API_BASE_URL}/api/documents`);
        if (search) url.searchParams.set('search', search);
        url.searchParams.set('page', '1');
        url.searchParams.set('limit', '50');

        const response = await fetch(url, {
            headers: {
                'Authorization': `Bearer ${token}`,
                'Content-Type': 'application/json'
            }
        });

        if (!response.ok) {
            const data = await response.json().catch(() => ({ detail: 'Unable to load documents.' }));
            throw new Error(data.detail || 'Unable to load documents.');
        }

        const result = await response.json();
        let items = Array.isArray(result.items) ? [...result.items] : [];

        if (filter !== 'all') {
            items = items.filter((doc) => (doc.file_type || '').toLowerCase() === filter.toLowerCase());
        }

        if (sort === 'oldest') {
            items.sort((a, b) => new Date(a.upload_date) - new Date(b.upload_date));
        } else if (sort === 'name') {
            items.sort((a, b) => (a.original_filename || '').localeCompare(b.original_filename || ''));
        } else {
            items.sort((a, b) => new Date(b.upload_date) - new Date(a.upload_date));
        }

        state.documents = items;
        renderDocuments(items);
    } catch (error) {
        console.error(error);
        renderEmptyState();
    }
}

function renderDocuments(items) {
    const tbody = document.getElementById('documentsTableBody');
    if (!tbody) return;

    if (!items.length) {
        renderEmptyState();
        return;
    }

    tbody.innerHTML = items.map((doc) => {
        const status = (doc.processing_status || 'processing').toLowerCase();
        const statusClass = status === 'processing' ? 'status-processing' : status === 'completed' ? 'status-completed' : 'status-failed';
        const canSummarize = status === 'completed';
        const summarizeTooltip = canSummarize ? '' : 'title="Document is still processing."';
        return `
            <tr>
                <td>
                    <div class="d-flex align-items-center gap-3">
                        <div class="selected-file-icon"><i class="fas fa-file-${getFileIcon(doc.file_type)}"></i></div>
                        <div>
                            <div class="fw-semibold text-dark">${escapeHtml(doc.original_filename || doc.filename)}</div>
                            <div class="small text-muted">${escapeHtml(doc.filename)}</div>
                        </div>
                    </div>
                </td>
                <td><span class="badge bg-light text-dark rounded-pill">${escapeHtml((doc.file_type || 'file').toUpperCase())}</span></td>
                <td>${formatFileSize(doc.file_size || 0)}</td>
                <td>${new Date(doc.upload_date).toLocaleDateString()}</td>
                <td><span class="document-status-badge ${statusClass}">${titleCase(status)}</span></td>
                <td>
                    <div class="action-btns d-flex flex-wrap gap-2">
                        <button class="btn btn-sm btn-outline-primary" data-action="view" data-id="${doc.id}">View</button>
                        <button class="btn btn-sm btn-outline-secondary" data-action="download" data-id="${doc.id}">Download</button>
                        <button class="btn btn-sm btn-outline-info" data-action="summarize" data-id="${doc.id}" ${canSummarize ? '' : 'disabled'} ${summarizeTooltip}>Summarize</button>
                        <button class="btn btn-sm btn-outline-danger" data-action="delete" data-id="${doc.id}">Delete</button>
                    </div>
                </td>
            </tr>
        `;
    }).join('');

    tbody.querySelectorAll('button[data-action]').forEach((button) => {
        button.addEventListener('click', async () => {
            const action = button.dataset.action;
            const id = Number(button.dataset.id);
            if (action === 'view') {
                const doc = state.documents.find((item) => Number(item.id) === id);
                await viewDocument(id, doc ? doc.file_type : '');
            }
            if (action === 'download') await downloadDocument(id);
            if (action === 'summarize') await summarizeDocument(id);
            if (action === 'delete') await deleteDocument(id);
        });
    });
}

function renderEmptyState() {
    const tbody = document.getElementById('documentsTableBody');
    if (!tbody) return;
    tbody.innerHTML = `
        <tr>
            <td colspan="6" class="text-center py-5">
                <div class="empty-state-box">
                    <div class="empty-state-icon"><i class="fas fa-folder-open"></i></div>
                    <div class="empty-state-title">No documents yet</div>
                    <div class="empty-state-desc">Upload your first business document to start using AI-powered document intelligence.</div>
                    <button class="btn btn-primary rounded-pill px-4" id="emptyUploadButton">Upload Document</button>
                </div>
            </td>
        </tr>
    `;

    document.getElementById('emptyUploadButton')?.addEventListener('click', () => {
        document.getElementById('documentFileInput')?.click();
    });
}

async function getDocumentViewToken(documentId) {
    const token = localStorage.getItem('access_token');
    const response = await fetch(`${API_BASE_URL}/api/documents/${documentId}/view-token`, {
        headers: {
            'Authorization': `Bearer ${token}`,
            'Content-Type': 'application/json'
        }
    });

    if (!response.ok) {
        const data = await response.json().catch(() => ({ detail: 'Unable to open this document.' }));
        throw new Error(data.detail || 'Unable to open this document.');
    }

    const data = await response.json();
    return data.token;
}

async function viewDocument(documentId, fileType) {
    const normalizedType = (fileType || '').toLowerCase();

    if (normalizedType === 'pdf') {
        try {
            const token = await getDocumentViewToken(documentId);
            const viewUrl = `${API_BASE_URL}/api/documents/${documentId}/view?token=${encodeURIComponent(token)}`;
            window.open(viewUrl, '_blank', 'noopener,noreferrer');
            return;
        } catch (error) {
            showToast(error.message || 'Unable to open this PDF.');
            return;
        }
    }

    if (normalizedType === 'txt') {
        const token = localStorage.getItem('access_token');
        const response = await fetch(`${API_BASE_URL}/api/documents/${documentId}/preview`, {
            headers: { 'Authorization': `Bearer ${token}` }
        });

        if (!response.ok) {
            showToast('Unable to preview this text file.');
            return;
        }

        const data = await response.json();
        const previewWindow = window.open('', '_blank', 'noopener,noreferrer');
        if (previewWindow) {
            previewWindow.document.write(`<pre style="white-space:pre-wrap; padding:24px; font-family:Segoe UI, sans-serif;">${escapeHtml(data.content || '')}</pre>`);
            previewWindow.document.title = 'Text Preview';
        }
        return;
    }

    showToast('Preview is not available for this file type. Please download the file.');
}

async function openDocumentModal(documentId) {
    const token = localStorage.getItem('access_token');
    const response = await fetch(`${API_BASE_URL}/api/documents/${documentId}`, {
        headers: { 'Authorization': `Bearer ${token}` }
    });
    if (!response.ok) {
        showToast('Unable to load document details.');
        return;
    }
    const document = await response.json();

    const detailContent = document.getElementById('documentDetailContent');
    if (!detailContent) return;

    detailContent.innerHTML = `
        <div class="row g-3">
            <div class="col-md-6"><strong>File Name</strong><div>${escapeHtml(document.original_filename || document.filename)}</div></div>
            <div class="col-md-6"><strong>Original File Name</strong><div>${escapeHtml(document.original_filename || '-')}</div></div>
            <div class="col-md-3"><strong>Type</strong><div>${escapeHtml((document.file_type || 'file').toUpperCase())}</div></div>
            <div class="col-md-3"><strong>Size</strong><div>${formatFileSize(document.file_size || 0)}</div></div>
            <div class="col-md-3"><strong>Uploaded</strong><div>${new Date(document.upload_date).toLocaleDateString()}</div></div>
            <div class="col-md-3"><strong>Status</strong><div>${titleCase(document.processing_status || 'processing')}</div></div>
            <div class="col-12"><strong>Processing Error</strong><div>${escapeHtml(document.processing_error || 'None')}</div></div>
        </div>
        <div class="mt-4 d-flex gap-2">
            <button class="btn btn-primary" data-preview-id="${document.id}" data-file-type="${document.file_type || 'file'}">Preview</button>
            <button class="btn btn-outline-secondary" data-download-id="${document.id}">Download</button>
            <button class="btn btn-outline-danger" data-delete-id="${document.id}">Delete</button>
        </div>
    `;

    detailContent.querySelector('[data-preview-id]')?.addEventListener('click', () => viewDocument(documentId, detailContent.querySelector('[data-preview-id]').dataset.fileType));
    detailContent.querySelector('[data-download-id]')?.addEventListener('click', () => downloadDocument(documentId));
    detailContent.querySelector('[data-delete-id]')?.addEventListener('click', () => deleteDocument(documentId));

    const modal = new bootstrap.Modal(document.getElementById('documentDetailsModal'));
    modal.show();
}

async function previewDocument(documentId) {
    const token = localStorage.getItem('access_token');
    const response = await fetch(`${API_BASE_URL}/api/documents/${documentId}/preview`, {
        headers: { 'Authorization': `Bearer ${token}` }
    });

    if (!response.ok) {
        showToast('Unable to preview this document.');
        return;
    }

    const data = await response.json();
    const content = document.getElementById('documentPreviewContent');
    if (!content) return;

    if (data.type === 'txt') {
        content.innerHTML = `<div class="preview-box">${escapeHtml(data.content || '')}</div>`;
    } else if (data.type === 'pdf') {
        const tokenValue = await getDocumentViewToken(documentId);
        const viewUrl = `${API_BASE_URL}/api/documents/${documentId}/view?token=${encodeURIComponent(tokenValue)}`;
        content.innerHTML = `
            <div class="preview-placeholder">
                <div>
                    <div class="mb-2"><i class="fas fa-file-pdf fa-2x text-danger"></i></div>
                    <div>PDF preview is not available in this browser.</div>
                </div>
            </div>
            <div class="mt-3 d-flex justify-content-end gap-2">
                <button class="btn btn-primary" type="button" onclick="window.open('${viewUrl}', '_blank', 'noopener,noreferrer')">Open PDF</button>
                <a class="btn btn-outline-secondary" href="${API_BASE_URL}/api/documents/${documentId}/download" target="_blank" rel="noopener">Download</a>
            </div>
        `;
    } else {
        content.innerHTML = `
            <div class="preview-placeholder">
                <div>
                    <div class="mb-2"><i class="fas fa-file-alt fa-2x text-secondary"></i></div>
                    <div>Preview is not available for this file type. Please download the file.</div>
                </div>
            </div>
            <div class="mt-3 text-end">
                <a class="btn btn-primary" href="${API_BASE_URL}/api/documents/${documentId}/download" target="_blank" rel="noopener">Download</a>
            </div>
        `;
    }

    const modal = new bootstrap.Modal(document.getElementById('documentPreviewModal'));
    modal.show();
}

async function downloadDocument(documentId) {
    const token = localStorage.getItem('access_token');
    try {
        const response = await fetch(`${API_BASE_URL}/api/documents/${documentId}/download`, {
            headers: {
                'Authorization': `Bearer ${token}`
            }
        });

        if (!response.ok) {
            const data = await response.json().catch(() => ({ detail: 'Download failed.' }));
            throw new Error(data.detail || 'Download failed.');
        }

        const blob = await response.blob();
        const url = window.URL.createObjectURL(blob);
        const anchor = document.createElement('a');
        anchor.href = url;
        anchor.download = '';
        anchor.rel = 'noopener';
        document.body.appendChild(anchor);
        anchor.click();
        anchor.remove();
        window.URL.revokeObjectURL(url);
    } catch (error) {
        console.error(error);
        showToast(error.message || 'Download failed.');
    }
}

async function summarizeDocument(documentId) {
    const token = localStorage.getItem('access_token');
    if (!token) {
        window.location.href = 'login.html';
        return;
    }

    const button = document.querySelector(`button[data-action="summarize"][data-id="${documentId}"]`);
    if (button) {
        button.disabled = true;
        button.textContent = 'Analyzing...';
    }

    showToast('Analyzing your document...');

    try {
        const response = await fetch(`${API_BASE_URL}/api/documents/${documentId}/summarize`, {
            method: 'POST',
            headers: {
                'Authorization': `Bearer ${token}`,
                'Content-Type': 'application/json'
            }
        });

        const data = await response.json().catch(() => ({}));
        if (!response.ok) {
            throw new Error(data.detail || 'Unable to generate the summary right now.');
        }

        window.location.href = `summary.html?document_id=${documentId}`;
    } catch (error) {
        console.error(error);
        showToast(error.message || 'Unable to generate the summary right now.');
        if (button) {
            button.disabled = false;
            button.textContent = 'Summarize';
        }
    }
}

async function deleteDocument(documentId) {
    const confirmed = window.confirm('Delete this document? This action cannot be undone.');
    if (!confirmed) return;

    const token = localStorage.getItem('access_token');
    try {
        const response = await fetch(`${API_BASE_URL}/api/documents/${documentId}`, {
            method: 'DELETE',
            headers: {
                'Authorization': `Bearer ${token}`,
                'Content-Type': 'application/json'
            }
        });

        const data = await response.json().catch(() => ({}));
        if (!response.ok) throw new Error(data.detail || 'Delete failed.');

        showToast(data.message || 'Document deleted successfully.');
        loadDocumentStats();
        loadDocuments();
    } catch (error) {
        console.error(error);
        showToast(error.message || 'Delete failed.');
    }
}

function logoutUser() {
    localStorage.removeItem('access_token');
    localStorage.removeItem('user');
    window.location.href = 'login.html';
}

function showToast(message) {
    alert(message);
}

function formatFileSize(bytes) {
    if (!bytes) return '0 KB';
    const units = ['B', 'KB', 'MB', 'GB'];
    let value = bytes;
    let unitIndex = 0;
    while (value >= 1024 && unitIndex < units.length - 1) {
        value /= 1024;
        unitIndex++;
    }
    return `${value.toFixed(1)} ${units[unitIndex]}`;
}

function getInitials(name) {
    const parts = (name || 'User').split(' ');
    return parts.slice(0, 2).map(part => part[0]).join('').toUpperCase();
}

function getFileIcon(fileType) {
    const map = {
        pdf: 'pdf',
        docx: 'word',
        txt: 'text',
        xlsx: 'excel',
        pptx: 'powerpoint',
    };
    return map[fileType] || 'alt';
}

function titleCase(value) {
    return String(value || '').replace(/\b\w/g, (char) => char.toUpperCase());
}

function escapeHtml(value) {
    return String(value ?? '').replace(/[&<>"']/g, (char) => ({
        '&': '&amp;',
        '<': '&lt;',
        '>': '&gt;',
        '"': '&quot;',
        "'": '&#39;'
    }[char]));
}
