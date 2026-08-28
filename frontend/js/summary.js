const API_BASE_URL = "https://intellibusiness-db.onrender.com";
document.addEventListener('DOMContentLoaded', () => {
    loadSummary();
    bindActions();
});

function getDocumentIdFromUrl() {
    const params = new URLSearchParams(window.location.search);
    return Number(params.get('document_id'));
}

async function loadSummary() {
    const documentId = getDocumentIdFromUrl();
    const token = localStorage.getItem('access_token');

    if (!documentId || !token) {
        showSummaryError('Your session has expired or the document is unavailable.');
        return;
    }

    toggleLoading(true);

    try {
        const response = await fetch(`${API_BASE_URL}/api/documents/${documentId}/summary`, {
            headers: {
                'Authorization': `Bearer ${token}`,
                'Content-Type': 'application/json'
            }
        });

        const data = await response.json().catch(() => ({}));
        if (!response.ok) {
            throw new Error(data.detail || 'Unable to load the summary.');
        }

        displaySummary(data);
    } catch (error) {
        showSummaryError(error.message || 'Unable to load the summary.');
    } finally {
        toggleLoading(false);
    }
}

function displaySummary(data) {
    const summaryContent = document.getElementById('summaryContent');
    if (!summaryContent) return;

    const filename = data.filename || 'Document';
    const createdAt = data.created_at ? new Date(data.created_at).toLocaleDateString('en-GB', {
        day: '2-digit',
        month: 'short',
        year: 'numeric'
    }) : 'N/A';

    document.getElementById('summaryDocumentName').textContent = filename;
    document.getElementById('summaryGeneratedAt').textContent = createdAt;
    document.getElementById('executiveSummaryText').textContent = data.executive_summary || 'Not specified in the document.';

    renderList(document.getElementById('keyPointsList'), data.key_points || []);
    renderList(document.getElementById('importantInfoList'), data.important_information || []);
    renderList(document.getElementById('actionItemsList'), data.action_items || []);

    const keywordsWrap = document.getElementById('keywordsList');
    keywordsWrap.innerHTML = '';
    if (Array.isArray(data.keywords) && data.keywords.length) {
        const badges = data.keywords.map((keyword) => `<span class="keyword-badge">${escapeHtml(keyword)}</span>`).join('');
        keywordsWrap.innerHTML = badges;
    } else {
        keywordsWrap.innerHTML = '<span class="keyword-badge">Not specified in the document.</span>';
    }

    summaryContent.classList.remove('d-none');
    document.getElementById('summaryErrorState').classList.add('d-none');
}

function renderList(element, items) {
    if (!element) return;
    element.innerHTML = '';

    if (!Array.isArray(items) || !items.length) {
        element.innerHTML = '<li>Not specified in the document.</li>';
        return;
    }

    element.innerHTML = items.map((item) => `<li>${escapeHtml(item || 'Not specified in the document.')}</li>`).join('');
}

function toggleLoading(isLoading) {
    const loadingState = document.getElementById('summaryLoadingState');
    const summaryContent = document.getElementById('summaryContent');
    if (loadingState) {
        loadingState.classList.toggle('d-none', !isLoading);
    }
    if (summaryContent) {
        summaryContent.classList.toggle('d-none', isLoading);
    }
}

function showSummaryError(message) {
    const errorState = document.getElementById('summaryErrorState');
    if (errorState) {
        errorState.textContent = message;
        errorState.classList.remove('d-none');
    }
}

function bindActions() {
    document.getElementById('copySummaryBtn')?.addEventListener('click', copySummary);
    document.getElementById('downloadSummaryBtn')?.addEventListener('click', downloadSummary);
    document.getElementById('regenerateSummaryBtn')?.addEventListener('click', regenerateSummary);
}

async function regenerateSummary() {
    const documentId = getDocumentIdFromUrl();
    const token = localStorage.getItem('access_token');
    if (!documentId || !token) {
        showSummaryError('Your session has expired or the document is unavailable.');
        return;
    }

    toggleLoading(true);
    try {
        const response = await fetch(`${API_BASE_URL}/api/documents/${documentId}/summarize?regenerate=true`, {
            method: 'POST',
            headers: {
                'Authorization': `Bearer ${token}`,
                'Content-Type': 'application/json'
            }
        });
        const data = await response.json().catch(() => ({}));
        if (!response.ok) {
            throw new Error(data.detail || 'Unable to regenerate the summary.');
        }
        displaySummary(data);
        showToast('Summary regenerated successfully.');
    } catch (error) {
        showSummaryError(error.message || 'Unable to regenerate the summary.');
        showToast(error.message || 'Unable to regenerate the summary.');
    } finally {
        toggleLoading(false);
    }
}

function buildSummaryText() {
    const documentName = document.getElementById('summaryDocumentName')?.textContent || 'Document';
    const generatedAt = document.getElementById('summaryGeneratedAt')?.textContent || 'N/A';
    const executiveSummary = document.getElementById('executiveSummaryText')?.textContent || '';
    const keyPoints = Array.from(document.querySelectorAll('#keyPointsList li')).map((item) => item.textContent.trim());
    const importantInfo = Array.from(document.querySelectorAll('#importantInfoList li')).map((item) => item.textContent.trim());
    const actionItems = Array.from(document.querySelectorAll('#actionItemsList li')).map((item) => item.textContent.trim());
    const keywords = Array.from(document.querySelectorAll('#keywordsList .keyword-badge')).map((item) => item.textContent.trim());

    return [
        'DOCUMENT SUMMARY',
        '',
        `Document: ${documentName}`,
        `Generated: ${generatedAt}`,
        '',
        'EXECUTIVE SUMMARY',
        executiveSummary,
        '',
        'KEY POINTS',
        ...keyPoints.map((point) => `• ${point}`),
        '',
        'IMPORTANT INFORMATION',
        ...importantInfo.map((info) => `• ${info}`),
        '',
        'ACTION ITEMS',
        ...actionItems.map((item) => `• ${item}`),
        '',
        'KEYWORDS',
        keywords.join(', ')
    ].join('\n');
}

async function copySummary() {
    const summaryText = buildSummaryText();
    try {
        await navigator.clipboard.writeText(summaryText);
        showToast('Summary copied to clipboard.');
    } catch (error) {
        showToast('Unable to copy summary to clipboard.');
    }
}

function downloadSummary() {
    const documentId = getDocumentIdFromUrl();
    const token = localStorage.getItem('access_token');
    if (!documentId || !token) {
        showSummaryError('Your session has expired or the document is unavailable.');
        return;
    }

    (async () => {
        toggleLoading(true);
        try {
            const response = await fetch(`${API_BASE_URL}/api/documents/${documentId}/summary/pdf`, {
                method: 'GET',
                headers: {
                    'Authorization': `Bearer ${token}`
                }
            });

            if (!response.ok) {
                const data = await response.json().catch(() => ({}));
                throw new Error(data.detail || 'Unable to download summary PDF.');
            }

            const blob = await response.blob();
            const url = URL.createObjectURL(blob);
            const link = document.createElement('a');
            link.href = url;
            // Try to get filename from content-disposition
            const cd = response.headers.get('Content-Disposition') || '';
            const match = cd.match(/filename="?([^";]+)"?/);
            const filename = match ? match[1] : `${document.getElementById('summaryDocumentName')?.textContent || 'document'}_summary.pdf`;
            link.download = filename;
            document.body.appendChild(link);
            link.click();
            document.body.removeChild(link);
            URL.revokeObjectURL(url);
            showToast('Summary PDF downloaded successfully.');
        } catch (error) {
            showSummaryError(error.message || 'Unable to download summary PDF.');
            showToast(error.message || 'Unable to download summary PDF.');
        } finally {
            toggleLoading(false);
        }
    })();
}

function showToast(message) {
    alert(message);
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
