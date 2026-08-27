const API_BASE_URL = 'http://127.0.0.1:8000';

window.addEventListener('DOMContentLoaded', initSettings);

async function initSettings() {
    const token = localStorage.getItem('access_token');
    if (!token) return redirectToLogin();
    
    // Get role from localStorage first if available
    let userRole = 'user';
    try {
        const userData = localStorage.getItem('user');
        if (userData) {
            const parsed = JSON.parse(userData);
            userRole = parsed.role || 'user';
        }
    } catch (e) {
        console.error('Error parsing cached user data:', e);
    }
    
    // Switch sidebar immediately based on cached role
    if (userRole === 'admin') {
        showAdminSidebar();
    } else {
        showUserSidebar();
    }
    
    bindSettingsEvents();
    
    try {
        const [profileResponse, preferencesResponse] = await Promise.all([apiFetch('/api/settings/profile'), apiFetch('/api/settings/preferences')]);
        if (!profileResponse.ok || !preferencesResponse.ok) throw new Error('Unable to load settings.');
        const profile = await profileResponse.json();
        const preferences = await preferencesResponse.json();
        
        console.log('User profile loaded:', profile);
        
        // Update sidebar if role changed
        if (profile.role !== userRole) {
            console.log(`Role changed from ${userRole} to ${profile.role}`);
            if (profile.role === 'admin') {
                showAdminSidebar();
            } else {
                showUserSidebar();
            }
        }
        
        // Cache user data for next load
        localStorage.setItem('user', JSON.stringify(profile));
        
        renderProfile(profile);
        renderPreferences(preferences);
    } catch (error) {
        console.error('Error in initSettings:', error);
        showAlert(error.message, 'danger');
    }
}

function showAdminSidebar() {
    console.log('Activating admin sidebar');
    
    const userSidebar = document.getElementById('userSidebar');
    const adminSidebar = document.getElementById('adminSidebar');
    const mobileSidebar = document.getElementById('mobileSidebar');
    const adminMobileSidebar = document.getElementById('adminMobileSidebar');
    
    // Show admin, hide user
    if (userSidebar) {
        userSidebar.style.display = 'none';
        userSidebar.classList.add('d-none');
    }
    if (adminSidebar) {
        adminSidebar.style.display = 'block';
        adminSidebar.classList.remove('d-none');
    }
    if (mobileSidebar) {
        mobileSidebar.style.display = 'none';
        mobileSidebar.classList.add('d-none');
    }
    if (adminMobileSidebar) {
        adminMobileSidebar.style.display = 'block';
        adminMobileSidebar.classList.remove('d-none');
    }
    
    // Update mobile toggle button
    const mobileToggleBtn = document.querySelector('.mobile-toggle-btn');
    if (mobileToggleBtn) {
        mobileToggleBtn.setAttribute('data-bs-target', '#adminMobileSidebar');
    }
    
    // Bind admin logout buttons
    const adminLogoutBtn = document.getElementById('adminLogoutBtn');
    const adminLogoutMobile = document.getElementById('adminLogoutMobile');
    if (adminLogoutBtn) {
        adminLogoutBtn.removeEventListener('click', logout);
        adminLogoutBtn.addEventListener('click', logout);
    }
    if (adminLogoutMobile) {
        adminLogoutMobile.removeEventListener('click', logout);
        adminLogoutMobile.addEventListener('click', logout);
    }
    
    console.log('Admin sidebar activated');
}

function showUserSidebar() {
    console.log('Activating user sidebar');
    
    const userSidebar = document.getElementById('userSidebar');
    const adminSidebar = document.getElementById('adminSidebar');
    const mobileSidebar = document.getElementById('mobileSidebar');
    const adminMobileSidebar = document.getElementById('adminMobileSidebar');
    
    // Show user, hide admin
    if (userSidebar) {
        userSidebar.style.display = 'block';
        userSidebar.classList.remove('d-none');
    }
    if (adminSidebar) {
        adminSidebar.style.display = 'none';
        adminSidebar.classList.add('d-none');
    }
    if (mobileSidebar) {
        mobileSidebar.style.display = 'block';
        mobileSidebar.classList.remove('d-none');
    }
    if (adminMobileSidebar) {
        adminMobileSidebar.style.display = 'none';
        adminMobileSidebar.classList.add('d-none');
    }
    
    // Update mobile toggle button
    const mobileToggleBtn = document.querySelector('.mobile-toggle-btn');
    if (mobileToggleBtn) {
        mobileToggleBtn.setAttribute('data-bs-target', '#mobileSidebar');
    }
    
    // Bind user logout buttons
    const logoutBtn = document.getElementById('logoutBtn');
    const logoutMobile = document.getElementById('logoutMobile');
    if (logoutBtn) {
        logoutBtn.removeEventListener('click', logout);
        logoutBtn.addEventListener('click', logout);
    }
    if (logoutMobile) {
        logoutMobile.removeEventListener('click', logout);
        logoutMobile.addEventListener('click', logout);
    }
    
    console.log('User sidebar activated');
}

function apiFetch(path, options = {}) {
    return fetch(`${API_BASE_URL}${path}`, { ...options, headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${localStorage.getItem('access_token')}`, ...(options.headers || {}) } });
}

function renderProfile(profile) {
    document.getElementById('fullName').value = profile.full_name || '';
    document.getElementById('companyName').value = profile.company_name || '';
    document.getElementById('email').value = profile.email || '';
    if (profile.role === 'admin') {
        document.getElementById('adminSettingsSection').classList.remove('d-none');
        document.getElementById('adminEmail').textContent = profile.email;
    }
    const preview = document.getElementById('profilePicturePreview');
    if (profile.profile_picture) preview.innerHTML = `<img src="${profile.profile_picture}" alt="Profile picture">`;
    else preview.textContent = (profile.full_name || 'U').charAt(0).toUpperCase();
}

function renderPreferences(preferences) {
    document.getElementById('aiResponseStyle').value = preferences.ai_response_style;
    document.getElementById('emailTone').value = preferences.default_email_tone;
    document.getElementById('emailNotifications').checked = preferences.email_notifications;
    document.getElementById('workflowNotifications').checked = preferences.workflow_notifications;
    document.getElementById('documentNotifications').checked = preferences.document_notifications;
}

function bindSettingsEvents() {
    document.getElementById('profileForm').addEventListener('submit', saveProfile);
    document.getElementById('savePreferences').addEventListener('click', savePreferences);
    document.getElementById('saveNotifications').addEventListener('click', savePreferences);
    document.getElementById('choosePicture').addEventListener('click', () => document.getElementById('profilePictureInput').click());
    document.getElementById('profilePictureInput').addEventListener('change', previewPicture);
    document.getElementById('passwordForm').addEventListener('submit', changePassword);
    document.getElementById('deleteAccount').addEventListener('click', () => bootstrap.Modal.getOrCreateInstance(document.getElementById('deleteModal')).show());
    document.getElementById('confirmDelete').addEventListener('click', deleteAccount);
    // Logout button binding is handled in showAdminSidebar() and showUserSidebar()
}

async function saveProfile(event) {
    event.preventDefault();
    const response = await apiFetch('/api/settings/profile', { method: 'PUT', body: JSON.stringify({ full_name: document.getElementById('fullName').value.trim(), company_name: document.getElementById('companyName').value.trim(), profile_picture: document.getElementById('profilePicturePreview').querySelector('img')?.src || null }) });
    const data = await response.json();
    if (!response.ok) return showAlert(data.detail || 'Unable to save profile.', 'danger');
    localStorage.setItem('user', JSON.stringify(data));
    renderProfile(data);
    showAlert('Profile settings saved successfully.', 'success');
}

async function savePreferences(event) {
    event?.preventDefault();
    const data = { theme: 'light', ai_response_style: document.getElementById('aiResponseStyle').value, default_email_tone: document.getElementById('emailTone').value, email_notifications: document.getElementById('emailNotifications').checked, workflow_notifications: document.getElementById('workflowNotifications').checked, document_notifications: document.getElementById('documentNotifications').checked };
    const response = await apiFetch('/api/settings/preferences', { method: 'PUT', body: JSON.stringify(data) });
    const result = await response.json();
    if (!response.ok) return showAlert(result.detail || 'Unable to save preferences.', 'danger');
    localStorage.setItem('user_preferences', JSON.stringify(result));
    localStorage.removeItem('theme');
    showAlert('Preferences saved successfully.', 'success');
}

function previewPicture(event) {
    const file = event.target.files[0];
    if (!file || file.size > 2 * 1024 * 1024) return showAlert('Choose an image up to 2 MB.', 'danger');
    const reader = new FileReader();
    reader.onload = () => { document.getElementById('profilePicturePreview').innerHTML = `<img src="${reader.result}" alt="Profile picture">`; };
    reader.readAsDataURL(file);
}

async function changePassword(event) {
    event.preventDefault();
    const newPassword = document.getElementById('newPassword').value;
    const confirmPassword = document.getElementById('confirmPassword').value;
    if (newPassword.length < 6) return showAlert('New password must be at least 6 characters.', 'danger');
    if (newPassword !== confirmPassword) return showAlert('New passwords do not match.', 'danger');
    const response = await apiFetch('/api/settings/password', { method: 'PUT', body: JSON.stringify({ current_password: document.getElementById('currentPassword').value, new_password: newPassword, confirm_password: confirmPassword }) });
    const data = await response.json();
    if (!response.ok) return showAlert(data.detail || 'Unable to change password.', 'danger');
    document.getElementById('passwordForm').reset();
    showAlert(data.message, 'success');
}

async function deleteAccount() {
    const response = await apiFetch('/api/settings/account', { method: 'DELETE' });
    const data = await response.json();
    if (!response.ok) return showAlert(data.detail || 'Unable to delete account.', 'danger');
    logout();
}

function logout(event) { event?.preventDefault(); localStorage.removeItem('access_token'); localStorage.removeItem('user'); localStorage.removeItem('user_data'); redirectToLogin(); }
function redirectToLogin() { window.location.href = 'login.html'; }
function showAlert(message, type) { const alert = document.getElementById('settingsAlert'); alert.textContent = message; alert.className = `alert alert-${type}`; }
