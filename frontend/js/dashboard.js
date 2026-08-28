/**
 * IntelliBusiness - SaaS Dashboard Controller (Phase 3)
 */

const API_BASE_URL = "https://intellibusiness-db.onrender.com";
const INITIAL_ACTIVITY_LIMIT = 4;
let allDashboardActivities = [];
let isActivityExpanded = false;

document.addEventListener('DOMContentLoaded', async () => {
    // 1. JWT Authentication Verification & User Profile Fetch
    const token = localStorage.getItem('access_token');
    if (!token) {
        redirectToLogin();
        return;
    }

    try {
        const storedUser = localStorage.getItem('user');

        if (!storedUser) {
            throw new Error('User session not found');
        }

    const user = JSON.parse(storedUser);
        if (user.role === 'admin') {
            window.location.href = 'admin-dashboard.html';
            return;
        }
        renderUserInfo(user);
        initGreeting(user.full_name);
        
        // 2. Load Dashboard Statistics & Recent Activity
        loadDashboardStats(token);
        loadRecentActivity(token);
        
        // 3. Initialize Interactive Components
        initProductivityChart();
        initGettingStartedChecklist();
        initNotifications();
        initLogoutHandlers();

    } catch (error) {
        console.error('Authentication check failed:', error);
        clearAuthAndRedirect();
    }
});

/**
 * Fetches user profile from backend JWT protected endpoint
 */
async function fetchUserProfile(token) {
    const response = await fetch(`${API_BASE_URL}/api/auth/profile`, {
        method: 'GET',
        headers: {
            'Authorization': `Bearer ${token}`,
            'Content-Type': 'application/json'
        }
    });

    if (!response.ok) {
        throw new Error('Invalid or expired authentication session');
    }

    const user = await response.json();
    localStorage.setItem('user', JSON.stringify(user));
    return user;
}

/**
 * Renders user profile information in Topbar, Sidebar, and Profile Modal
 */
function renderUserInfo(user) {
    const initials = getInitials(user.full_name);
    
    // Topbar User Menu
    const topbarAvatar = document.getElementById('topbarUserAvatar');
    const topbarName = document.getElementById('topbarUserName');
    const topbarRole = document.getElementById('topbarUserRole');

    if (topbarAvatar) topbarAvatar.textContent = initials;
    if (topbarName) topbarName.textContent = user.full_name;
    if (topbarRole) topbarRole.textContent = user.company_name || 'Business User';

    // Profile Modal Details
    const modalName = document.getElementById('modalFullName');
    const modalCompany = document.getElementById('modalCompany');
    const modalEmail = document.getElementById('modalEmail');
    const modalRole = document.getElementById('modalRole');
    const modalDate = document.getElementById('modalCreatedDate');

    if (modalName) modalName.textContent = user.full_name;
    if (modalCompany) modalCompany.textContent = user.company_name;
    if (modalEmail) modalEmail.textContent = user.email;
    if (modalRole) modalRole.textContent = (user.role || 'user').toUpperCase();
    
    if (modalDate && user.created_at) {
        const dateObj = new Date(user.created_at);
        modalDate.textContent = dateObj.toLocaleDateString(undefined, {
            year: 'numeric', month: 'long', day: 'numeric'
        });
    }
}

/**
 * Renders time-of-day dynamic greeting
 */
function initGreeting(fullName) {
    const greetingText = document.getElementById('greetingText');
    const welcomeUserName = document.getElementById('welcomeUserName');
    
    const hour = new Date().getHours();
    let timeGreeting = 'Good morning';
    if (hour >= 12 && hour < 17) {
        timeGreeting = 'Good afternoon';
    } else if (hour >= 17) {
        timeGreeting = 'Good evening';
    }

    if (greetingText) greetingText.textContent = timeGreeting;
    if (welcomeUserName) welcomeUserName.textContent = fullName;
}

/**
 * Fetches statistics from GET /api/dashboard/stats
 */
async function loadDashboardStats(token) {
    try {
        const response = await fetch(`${API_BASE_URL}/api/dashboard/stats`, {
            method: 'GET',
            headers: {
                'Authorization': `Bearer ${token}`,
                'Content-Type': 'application/json'
            }
        });

        if (response.ok) {
            const stats = await response.json();
            animateCounter('statDocuments', stats.documents || 0);
            animateCounter('statAiTasks', stats.ai_tasks || 0);
            animateCounter('statEmails', stats.emails_generated || 0);
            animateCounter('statWorkflows', stats.workflows || 0);
        } else {
            fallbackStats();
        }
    } catch (err) {
        console.warn('Unable to load dashboard stats:', err);
        fallbackStats();
    }
}

function fallbackStats() {
    animateCounter('statDocuments', 0);
    animateCounter('statAiTasks', 0);
    animateCounter('statEmails', 0);
    animateCounter('statWorkflows', 0);
}

/**
 * Fetches recent activities from GET /api/dashboard/recent-activity
 */
async function loadRecentActivity(token) {
    const container = document.getElementById('recentActivityTimeline');
    if (!container) return;

    try {
        const response = await fetch(`${API_BASE_URL}/api/dashboard/recent-activity`, {
            method: 'GET',
            headers: {
                'Authorization': `Bearer ${token}`,
                'Content-Type': 'application/json'
            }
        });

        if (response.ok) {
            const activities = await response.json();
            if (Array.isArray(activities) && activities.length > 0) {
                allDashboardActivities = activities;
                isActivityExpanded = false;
                renderActivityTimeline(container, activities);
            } else {
                allDashboardActivities = [];
                renderEmptyActivityState(container);
            }
        } else {
            renderEmptyActivityState(container);
        }
    } catch (err) {
        console.warn('Unable to load recent activity:', err);
        renderEmptyActivityState(container);
    }
}

function renderActivityTimeline(container, activities) {
    const visibleActivities = isActivityExpanded ? activities : activities.slice(0, INITIAL_ACTIVITY_LIMIT);
    const toggle = document.getElementById('recentActivityToggle');
    if (toggle) {
        toggle.textContent = isActivityExpanded ? 'Show Less' : 'View All';
        toggle.hidden = activities.length <= INITIAL_ACTIVITY_LIMIT;
        toggle.setAttribute('aria-expanded', String(isActivityExpanded));
    }

    let html = `<div class="timeline-list${isActivityExpanded ? ' timeline-list-expanded' : ''}">`;
    visibleActivities.forEach(act => {
        html += `
            <div class="timeline-item">
                <div class="timeline-badge ${act.bg_color || 'bg-light'} ${act.icon_color || 'text-primary'}">
                    <i class="${act.icon || 'fas fa-circle'}"></i>
                </div>
                <div class="timeline-title">${escapeHtml(act.title)}</div>
                <div class="timeline-desc">${escapeHtml(act.description)}</div>
                <div class="timeline-time"><i class="far fa-clock me-1"></i>${escapeHtml(act.timestamp)}</div>
            </div>
        `;
    });
    html += '</div>';
    container.innerHTML = html;
}

function toggleRecentActivity(event) {
    event.preventDefault();
    if (allDashboardActivities.length <= INITIAL_ACTIVITY_LIMIT) return;

    isActivityExpanded = !isActivityExpanded;
    const container = document.getElementById('recentActivityTimeline');
    if (container) renderActivityTimeline(container, allDashboardActivities);
}

document.addEventListener('DOMContentLoaded', () => {
    const toggle = document.getElementById('recentActivityToggle');
    if (toggle) toggle.addEventListener('click', toggleRecentActivity);
});

function renderEmptyActivityState(container) {
    const toggle = document.getElementById('recentActivityToggle');
    if (toggle) toggle.hidden = true;
    container.innerHTML = `
        <div class="empty-state-box p-4 text-center">
            <div class="empty-state-icon text-muted mb-2 fs-2">
                <i class="fas fa-history"></i>
            </div>
            <div class="empty-state-title fw-bold text-dark mb-1">No recent activity yet</div>
            <div class="empty-state-desc text-muted small mb-3">Your uploaded documents, AI chat interactions, and generated emails will appear here automatically.</div>
            <a href="documents.html" class="btn btn-primary btn-sm rounded-pill px-3">
                <i class="fas fa-upload me-1"></i> Upload First Document
            </a>
        </div>
    `;
}

/**
 * Initializes Chart.js Productivity Chart with REAL-TIME data
 */
async function initProductivityChart() {
    const canvas = document.getElementById('productivityChart');
    if (!canvas) return;

    const token = localStorage.getItem('access_token');
    let labels = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];
    let aiTasksData = [0, 0, 0, 0, 0, 0, 0];
    let docsData = [0, 0, 0, 0, 0, 0, 0];

    try {
        const res = await fetch(`${API_BASE_URL}/api/dashboard/chart-data`, {
            headers: {
                'Authorization': `Bearer ${token}`,
                'Content-Type': 'application/json'
            }
        });
        if (res.ok) {
            const chartInfo = await res.json();
            labels = chartInfo.labels || labels;
            aiTasksData = chartInfo.ai_tasks || aiTasksData;
            docsData = chartInfo.documents || docsData;
        }
    } catch (e) {
        console.warn('Unable to load chart data:', e);
    }

    const ctx = canvas.getContext('2d');
    
    // Gradient definitions
    const gradientBlue = ctx.createLinearGradient(0, 0, 0, 300);
    gradientBlue.addColorStop(0, 'rgba(37, 99, 235, 0.35)');
    gradientBlue.addColorStop(1, 'rgba(37, 99, 235, 0.0)');

    const gradientPurple = ctx.createLinearGradient(0, 0, 0, 300);
    gradientPurple.addColorStop(0, 'rgba(124, 58, 237, 0.25)');
    gradientPurple.addColorStop(1, 'rgba(124, 58, 237, 0.0)');

    new Chart(ctx, {
        type: 'line',
        data: {
            labels: labels,
            datasets: [
                {
                    label: 'AI Tasks Processed',
                    data: aiTasksData,
                    borderColor: '#2563EB',
                    backgroundColor: gradientBlue,
                    borderWidth: 3,
                    fill: true,
                    tension: 0.4,
                    pointRadius: 4,
                    pointBackgroundColor: '#2563EB',
                    pointHoverRadius: 6
                },
                {
                    label: 'Documents Analyzed',
                    data: docsData,
                    borderColor: '#7C3AED',
                    backgroundColor: gradientPurple,
                    borderWidth: 2,
                    borderDash: [4, 4],
                    fill: true,
                    tension: 0.4,
                    pointRadius: 3,
                    pointBackgroundColor: '#7C3AED'
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    position: 'top',
                    align: 'end',
                    labels: {
                        usePointStyle: true,
                        boxWidth: 8,
                        font: { family: 'Poppins', size: 12 }
                    }
                },
                tooltip: {
                    backgroundColor: '#0F172A',
                    titleFont: { family: 'Poppins', size: 13, weight: '600' },
                    bodyFont: { family: 'Poppins', size: 12 },
                    padding: 10,
                    cornerRadius: 8
                }
            },
            scales: {
                x: {
                    grid: { display: false },
                    ticks: { font: { family: 'Poppins', size: 12 }, color: '#64748B' }
                },
                y: {
                    grid: { color: '#F1F5F9' },
                    ticks: { font: { family: 'Poppins', size: 12 }, color: '#64748B', precision: 0 },
                    beginAtZero: true
                }
            }
        }
    });
}


/**
 * Initializes Getting Started Checklist
 */
function initGettingStartedChecklist() {
    const checkboxes = document.querySelectorAll('.checklist-checkbox');
    const progressBar = document.getElementById('checklistProgressBar');
    const progressText = document.getElementById('checklistProgressText');

    // Restore checklist state from localStorage
    const savedState = JSON.parse(localStorage.getItem('intellibusiness_checklist_state') || '{}');

    checkboxes.forEach((cb, idx) => {
        const itemKey = `item_${idx}`;
        if (savedState[itemKey]) {
            cb.checked = true;
            cb.closest('.checklist-item').classList.add('completed');
        }

        cb.addEventListener('change', () => {
            savedState[itemKey] = cb.checked;
            localStorage.setItem('intellibusiness_checklist_state', JSON.stringify(savedState));
            
            if (cb.checked) {
                cb.closest('.checklist-item').classList.add('completed');
            } else {
                cb.closest('.checklist-item').classList.remove('completed');
            }

            updateProgress();
        });
    });

    function updateProgress() {
        const total = checkboxes.length;
        const checkedCount = document.querySelectorAll('.checklist-checkbox:checked').length;
        const percentage = Math.round((checkedCount / total) * 100);

        if (progressBar) progressBar.style.width = `${percentage}%`;
        if (progressText) progressText.textContent = `${checkedCount} of ${total} completed (${percentage}%)`;
    }

    updateProgress();
}

/**
 * Initializes Notification Dropdown Handlers
 */
function initNotifications() {
    const btnMarkAllRead = document.getElementById('btnMarkNotificationsRead');
    const badgeDot = document.getElementById('notificationBadgeDot');
    const countBadge = document.getElementById('notificationCountBadge');

    if (btnMarkAllRead) {
        btnMarkAllRead.addEventListener('click', (e) => {
            e.preventDefault();
            if (badgeDot) badgeDot.style.display = 'none';
            if (countBadge) {
                countBadge.textContent = '0 Unread';
                countBadge.className = 'badge bg-secondary-subtle text-secondary rounded-pill';
            }
        });
    }
}

/**
 * Initializes Logout Click Handlers across desktop & mobile menus
 */
function initLogoutHandlers() {
    const logoutBtnIds = ['btnLogoutTopbar', 'btnLogoutSidebar', 'btnLogoutMobile', 'btnLogoutModal'];
    
    logoutBtnIds.forEach(id => {
        const btn = document.getElementById(id);
        if (btn) {
            btn.addEventListener('click', (e) => {
                e.preventDefault();
                clearAuthAndRedirect();
            });
        }
    });
}

/**
 * Clears JWT session storage and redirects to login page
 */
function clearAuthAndRedirect() {
    localStorage.removeItem('access_token');
    localStorage.removeItem('user');
    window.location.href = 'login.html';
}

function redirectToLogin() {
    window.location.href = 'login.html';
}

/**
 * Helper: Generates user initials (e.g. "John Doe" -> "JD")
 */
function getInitials(name) {
    if (!name) return 'IB';
    const parts = name.trim().split(' ');
    if (parts.length >= 2) {
        return (parts[0][0] + parts[1][0]).toUpperCase();
    }
    return name.substring(0, 2).toUpperCase();
}

/**
 * Helper: Animate number counter for statistics
 */
function animateCounter(elementId, targetValue) {
    const el = document.getElementById(elementId);
    if (!el) return;

    let start = 0;
    const duration = 1000;
    const stepTime = 30;
    const steps = Math.ceil(duration / stepTime);
    const increment = targetValue / steps;

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

/**
 * Helper: Escape HTML string to prevent XSS
 */
function escapeHtml(str) {
    if (!str) return '';
    return str
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;");
}
