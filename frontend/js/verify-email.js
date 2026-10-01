const API_BASE_URL = window.INTELLIBUSINESS_API_BASE_URL || (
    ["localhost", "127.0.0.1"].includes(window.location.hostname)
        ? "http://127.0.0.1:8000"
        : "https://intellibusiness-db.onrender.com"
);

document.addEventListener('DOMContentLoaded', async () => {
    const status = document.getElementById('verificationStatus');
    const loginLink = document.getElementById('loginLink');
    const token = new URLSearchParams(window.location.hash.slice(1)).get('token');
    window.history.replaceState({}, document.title, window.location.pathname);

    if (!token) {
        showResult('This verification link is missing or invalid. Request a new link from the login page.');
        return;
    }

    try {
        const response = await fetch(`${API_BASE_URL}/api/auth/verify-email`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ token }),
        });
        const data = await response.json();
        if (!response.ok) throw new Error(data.detail || 'This verification link is invalid or expired.');
        showResult(data.message || 'Your email has been verified. You can now sign in.');
    } catch (error) {
        showResult(error.message || 'Unable to verify this email. Request a new link from the login page.');
    }

    function showResult(message) {
        status.textContent = message;
        loginLink.classList.remove('d-none');
    }
});