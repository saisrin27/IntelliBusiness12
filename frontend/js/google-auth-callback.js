const API_BASE_URL = window.INTELLIBUSINESS_API_BASE_URL || (
    ["localhost", "127.0.0.1"].includes(window.location.hostname)
        ? "http://127.0.0.1:8000"
        : "https://intellibusiness-db.onrender.com"
);

document.addEventListener('DOMContentLoaded', async () => {
    const status = document.getElementById('authStatus');
    const loginLink = document.getElementById('loginLink');
    const params = new URLSearchParams(window.location.hash.slice(1));
    const accessToken = params.get('access_token');
    window.history.replaceState({}, document.title, window.location.pathname);

    if (!accessToken) {
        showFailure('Google sign-in did not return a valid session. Please try again.');
        return;
    }

    localStorage.setItem('access_token', accessToken);
    try {
        const response = await fetch(`${API_BASE_URL}/api/auth/profile`, {
            headers: { Authorization: `Bearer ${accessToken}` },
        });
        if (!response.ok) throw new Error('Unable to load the signed-in account.');
        const user = await response.json();
        localStorage.setItem('user', JSON.stringify(user));
        window.location.replace(user.role === 'admin' ? 'admin-dashboard.html' : 'dashboard.html');
    } catch (error) {
        localStorage.removeItem('access_token');
        localStorage.removeItem('user');
        showFailure('Unable to complete sign-in. Please return to login and try again.');
    }

    function showFailure(message) {
        status.textContent = message;
        loginLink.classList.remove('d-none');
    }
});