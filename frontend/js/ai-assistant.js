const API_BASE_URL = "https://intellibusiness-db.onrender.com";

let currentConversationId = null;
let isSending = false;

document.addEventListener('DOMContentLoaded', () => {
    checkAuth();
    loadUserProfile();
    loadConversations();
    bindEvents();
});

function checkAuth() {
    const token = localStorage.getItem('access_token');
    if (!token) {
        window.location.href = 'login.html';
    }
}

async function loadUserProfile() {
    const userStr = localStorage.getItem('user') || localStorage.getItem('user_data');
    let user = null;

    try {
        user = userStr ? JSON.parse(userStr) : null;
        user = user?.user || user?.data || user;
    } catch (e) {
        console.error('Error parsing stored user profile:', e);
    }

    if (localStorage.getItem('access_token')) {
        try {
            const response = await fetch(`${API_BASE_URL}/api/auth/profile`, {
                headers: { 'Authorization': `Bearer ${localStorage.getItem('access_token')}` }
            });
            if (response.ok) {
                user = await response.json();
                localStorage.setItem('user', JSON.stringify(user));
            }
        } catch (e) {
            console.error('Unable to load user profile:', e);
        }
    }

    if (user) {
        const name = user.full_name || user.name || 'User';
        document.getElementById('profileModalName').textContent = name;
        document.getElementById('profileModalCompany').textContent = user.company_name || user.company || '-';
        document.getElementById('profileModalEmail').textContent = user.email || user.email_address || '-';
        document.getElementById('profileModalAvatar').textContent = name.charAt(0).toUpperCase();
    }
}

function bindEvents() {
    document.querySelectorAll('[data-bs-target="#profileModal"]').forEach((profileTrigger) => {
        profileTrigger.addEventListener('click', () => loadUserProfile());
    });

    document.querySelector('#mobileSidebar [data-bs-target="#profileModal"]')?.addEventListener('click', (event) => {
        event.preventDefault();
        const mobileSidebar = document.getElementById('mobileSidebar');
        const profileModal = document.getElementById('profileModal');
        bootstrap.Offcanvas.getOrCreateInstance(mobileSidebar).hide();
        mobileSidebar.addEventListener('hidden.bs.offcanvas', () => {
            bootstrap.Modal.getOrCreateInstance(profileModal).show();
        }, { once: true });
    });

    ['btnLogoutSidebar', 'btnLogoutMobile'].forEach((logoutId) => {
        const logoutBtn = document.getElementById(logoutId);
        if (logoutBtn) {
            logoutBtn.addEventListener('click', (event) => {
                event.preventDefault();
                localStorage.removeItem('access_token');
                localStorage.removeItem('user');
                localStorage.removeItem('user_data');
                window.location.href = 'login.html';
            });
        }
    });

    const newChatBtn = document.getElementById('newChatBtn');
    if (newChatBtn) {
        newChatBtn.addEventListener('click', createNewChat);
    }

    const chatForm = document.getElementById('chatForm');
    const chatInput = document.getElementById('chatInput');

    if (chatForm && chatInput) {
        chatForm.addEventListener('submit', (e) => {
            e.preventDefault();
            const message = chatInput.value ? chatInput.value.trim() : '';
            if (message && !isSending) {
                sendMessage(message);
            }
        });

        chatInput.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                chatForm.dispatchEvent(new Event('submit'));
            }
        });
    }

    // Suggested Questions Handler
    const suggestedGrid = document.getElementById('suggestedQuestionsGrid');
    if (suggestedGrid) {
        suggestedGrid.addEventListener('click', (e) => {
            const pill = e.target.closest('.suggestion-pill');
            if (pill && !isSending) {
                const question = pill.dataset.question || pill.textContent.trim();
                sendMessage(question);
            }
        });
    }
}

async function loadConversations() {
    const token = localStorage.getItem('access_token');
    const listEl = document.getElementById('conversationsList');
    if (!listEl) return;

    try {
        const response = await fetch(`${API_BASE_URL}/api/ai/conversations`, {
            headers: {
                'Authorization': `Bearer ${token}`,
                'Content-Type': 'application/json'
            }
        });

        if (!response.ok) throw new Error('Unable to load conversations.');
        const conversations = await response.json();

        renderConversationsList(conversations);
    } catch (error) {
        console.error(error);
    }
}

function renderConversationsList(conversations) {
    const listEl = document.getElementById('conversationsList');
    if (!listEl) return;

    if (!Array.isArray(conversations) || conversations.length === 0) {
        listEl.innerHTML = '<div class="text-muted small px-2 py-3 text-center">No recent conversations.</div>';
        return;
    }

    listEl.innerHTML = conversations.map((conv) => {
        const isActive = currentConversationId === conv.id ? 'active' : '';
        const title = escapeHtml(conv.title || 'Conversation');
        return `
            <div class="conversation-item ${isActive}" data-id="${conv.id}">
                <div class="d-flex align-items-center gap-2 overflow-hidden">
                    <i class="fas fa-message text-muted me-1"></i>
                    <span class="text-truncate">${title}</span>
                </div>
                <button class="btn-delete-conv" data-action="delete-conv" data-id="${conv.id}" title="Delete chat">
                    <i class="fas fa-trash-alt"></i>
                </button>
            </div>
        `;
    }).join('');

    listEl.querySelectorAll('.conversation-item').forEach((item) => {
        item.addEventListener('click', (e) => {
            if (e.target.closest('.btn-delete-conv')) return;
            const id = Number(item.dataset.id);
            if (id && id !== currentConversationId) {
                loadConversation(id);
            }
        });
    });

    listEl.querySelectorAll('.btn-delete-conv').forEach((btn) => {
        btn.addEventListener('click', async (e) => {
            e.stopPropagation();
            const id = Number(btn.dataset.id);
            if (id) {
                await deleteConversation(id);
            }
        });
    });
}

async function loadConversation(conversationId) {
    const token = localStorage.getItem('access_token');
    try {
        const response = await fetch(`${API_BASE_URL}/api/ai/conversations/${conversationId}`, {
            headers: {
                'Authorization': `Bearer ${token}`,
                'Content-Type': 'application/json'
            }
        });

        if (!response.ok) throw new Error('Unable to load conversation details.');
        const conv = await response.json();

        currentConversationId = conv.id;

        const messagesContainer = document.getElementById('chatMessages');
        messagesContainer.innerHTML = '';

        if (Array.isArray(conv.messages) && conv.messages.length > 0) {
            conv.messages.forEach((msg) => {
                renderMessage(msg.role, msg.content, msg.sources);
            });
        } else {
            showWelcomeScreen();
        }

        loadConversations();
        scrollToBottom();
    } catch (error) {
        console.error(error);
        alert(error.message || 'Unable to open conversation.');
    }
}

function createNewChat() {
    currentConversationId = null;
    
    const messagesContainer = document.getElementById('chatMessages');
    messagesContainer.innerHTML = '';
    showWelcomeScreen();

    const chatInput = document.getElementById('chatInput');
    if (chatInput) {
        chatInput.value = '';
        chatInput.focus();
    }

    loadConversations();
}

async function deleteConversation(conversationId) {
    if (!confirm('Delete this conversation history?')) return;

    const token = localStorage.getItem('access_token');
    try {
        const response = await fetch(`${API_BASE_URL}/api/ai/conversations/${conversationId}`, {
            method: 'DELETE',
            headers: {
                'Authorization': `Bearer ${token}`,
                'Content-Type': 'application/json'
            }
        });

        if (!response.ok) throw new Error('Unable to delete conversation.');

        if (currentConversationId === conversationId) {
            createNewChat();
        } else {
            loadConversations();
        }
    } catch (error) {
        alert(error.message || 'Unable to delete conversation.');
    }
}

async function sendMessage(messageText) {
    if (!messageText || isSending) return;

    const token = localStorage.getItem('access_token');
    const chatInput = document.getElementById('chatInput');
    const sendBtn = document.getElementById('sendBtn');

    hideWelcomeScreen();

    // 1. Render User Message
    renderMessage('user', messageText);
    chatInput.value = '';
    scrollToBottom();

    // 2. Render Typing Indicator
    isSending = true;
    if (sendBtn) sendBtn.disabled = true;
    const typingIndicatorEl = showTypingIndicator('Searching your documents...');
    scrollToBottom();

    try {
        setTimeout(() => {
            if (typingIndicatorEl) {
                const label = typingIndicatorEl.querySelector('.typing-text');
                if (label) label.textContent = 'Preparing answer...';
            }
        }, 1000);

        const response = await fetch(`${API_BASE_URL}/api/ai/chat`, {
            method: 'POST',
            headers: {
                'Authorization': `Bearer ${token}`,
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                message: messageText,
                conversation_id: currentConversationId
            })
        });

        const data = await response.json().catch(() => ({}));
        if (!response.ok) {
            throw new Error(data.detail || 'Something went wrong while searching your documents. Please try again.');
        }

        currentConversationId = data.conversation_id;

        removeTypingIndicator(typingIndicatorEl);
        renderMessage('assistant', data.message || 'No answer generated.', data.sources || []);
        
        loadConversations();
    } catch (error) {
        removeTypingIndicator(typingIndicatorEl);
        renderMessage('assistant', error.message || 'Something went wrong while searching your documents. Please try again.');
    } finally {
        isSending = false;
        if (sendBtn) sendBtn.disabled = false;
        chatInput.focus();
        scrollToBottom();
    }
}

function renderMessage(role, content, sources = []) {
    const messagesContainer = document.getElementById('chatMessages');
    if (!messagesContainer) return;

    const isUser = role === 'user';
    const messageRow = document.createElement('div');
    messageRow.className = `message-row ${isUser ? 'user' : 'assistant'}`;

    const avatarIcon = isUser ? '<i class="fas fa-user"></i>' : '<i class="fas fa-robot"></i>';
    
    let sourcesHtml = '';
    if (!isUser && Array.isArray(sources) && sources.length > 0) {
        const sourceBadges = sources.map((src) => {
            const filename = escapeHtml(src.filename || 'Document');
            return `<a class="source-badge" href="documents.html" title="View document"><i class="fas fa-file-lines me-1"></i> ${filename}</a>`;
        }).join('');

        sourcesHtml = `
            <div class="message-sources">
                <span class="fw-semibold text-muted me-1">Source${sources.length > 1 ? 's' : ''}:</span>
                ${sourceBadges}
            </div>
        `;
    }

    messageRow.innerHTML = `
        <div class="message-avatar">${avatarIcon}</div>
        <div class="message-bubble">
            <div>${formatMessageText(content)}</div>
            ${sourcesHtml}
        </div>
    `;

    messagesContainer.appendChild(messageRow);
}

function showTypingIndicator(initialText = 'Searching your documents...') {
    const messagesContainer = document.getElementById('chatMessages');
    if (!messagesContainer) return null;

    const indicator = document.createElement('div');
    indicator.className = 'message-row assistant typing-row';
    indicator.innerHTML = `
        <div class="message-avatar"><i class="fas fa-robot"></i></div>
        <div class="typing-indicator">
            <span class="spinner-border spinner-border-sm text-primary me-1" role="status"></span>
            <span class="typing-text">${escapeHtml(initialText)}</span>
        </div>
    `;
    messagesContainer.appendChild(indicator);
    return indicator;
}

function removeTypingIndicator(indicatorEl) {
    if (indicatorEl && indicatorEl.parentNode) {
        indicatorEl.parentNode.removeChild(indicatorEl);
    }
}

function showWelcomeScreen() {
    const welcomeScreen = document.getElementById('welcomeScreen');
    if (welcomeScreen) {
        welcomeScreen.classList.remove('d-none');
    }
}

function hideWelcomeScreen() {
    const welcomeScreen = document.getElementById('welcomeScreen');
    if (welcomeScreen) {
        welcomeScreen.classList.add('d-none');
    }
}

function scrollToBottom() {
    const messagesContainer = document.getElementById('chatMessages');
    if (messagesContainer) {
        messagesContainer.scrollTop = messagesContainer.scrollHeight;
    }
}

function formatMessageText(text) {
    if (!text) return '';
    const safeText = escapeHtml(text);
    return safeText
        .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
        .replace(/^\s*[\*\-]\s+(.*)$/gm, '• $1')
        .replace(/\n\n/g, '<br><br>')
        .replace(/\n/g, '<br>');
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
