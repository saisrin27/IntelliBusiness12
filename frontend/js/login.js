/**
 * IntelliBusiness - Login Controller
 */

const API_BASE_URL = 'http://127.0.0.1:8000';

document.addEventListener('DOMContentLoaded', async () => {
    // Redirect to dashboard if already logged in
    const existingToken = localStorage.getItem('access_token');
    if (existingToken) {
        try {
            const profileResponse = await fetch(`${API_BASE_URL}/api/auth/profile`, {
                headers: { 'Authorization': `Bearer ${existingToken}` }
            });
            if (!profileResponse.ok) throw new Error('Stored session is invalid');
            const storedUser = await profileResponse.json();
            localStorage.setItem('user', JSON.stringify(storedUser));
            window.location.href = storedUser.role === 'admin' ? 'admin-dashboard.html' : 'dashboard.html';
            return;
        } catch (error) {
            localStorage.removeItem('access_token');
            localStorage.removeItem('user');
            localStorage.removeItem('user_data');
        }
    }

    const loginForm = document.getElementById('loginForm');
    const emailInput = document.getElementById('email');
    const passwordInput = document.getElementById('password');
    const togglePasswordBtn = document.getElementById('togglePassword');
    const togglePasswordIcon = document.getElementById('togglePasswordIcon');
    const btnSubmit = document.getElementById('btnSubmit');
    const btnText = document.getElementById('btnText');
    const btnSpinner = document.getElementById('btnSpinner');
    const alertError = document.getElementById('alertError');
    const alertErrorMessage = document.getElementById('alertErrorMessage');
    const alertSuccess = document.getElementById('alertSuccess');

    // Toggle Password Visibility
    togglePasswordBtn.addEventListener('click', () => {
        const type = passwordInput.getAttribute('type') === 'password' ? 'text' : 'password';
        passwordInput.setAttribute('type', type);
        togglePasswordIcon.classList.toggle('fa-eye');
        togglePasswordIcon.classList.toggle('fa-eye-slash');
    });

    // Form Submission
    loginForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        hideAlerts();

        const email = emailInput.value.trim();
        const password = passwordInput.value;

        // Validation
        let isValid = true;
        if (!email || !validateEmail(email)) {
            emailInput.classList.add('is-invalid');
            isValid = false;
        } else {
            emailInput.classList.remove('is-invalid');
        }

        if (!password) {
            passwordInput.classList.add('is-invalid');
            isValid = false;
        } else {
            passwordInput.classList.remove('is-invalid');
        }

        if (!isValid) return;

        // Set Loading State
        setLoading(true);

        try {
            const response = await fetch(`${API_BASE_URL}/api/auth/login`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    email: email,
                    password: password
                })
            });

            const data = await response.json();

            if (!response.ok) {
                const errorDetail = data.detail || 'Login failed. Please check your credentials.';
                showError(errorDetail);
                setLoading(false);
                return;
            }

            // Store Token & User details
            localStorage.setItem('access_token', data.access_token);
            localStorage.setItem('user', JSON.stringify(data.user));

            showSuccess('Login successful! Redirecting to your dashboard...');

            const profileResponse = await fetch(`${API_BASE_URL}/api/auth/profile`, {
                headers: { 'Authorization': `Bearer ${data.access_token}` }
            });
            const profile = profileResponse.ok ? await profileResponse.json() : data.user;
            localStorage.setItem('user', JSON.stringify(profile));

            setTimeout(() => {
                window.location.href = profile.role === 'admin' ? 'admin-dashboard.html' : 'dashboard.html';
            }, 1000);

        } catch (error) {
            console.error('Login error:', error);
            showError('Unable to connect to backend server. Please make sure the FastAPI server is running on http://127.0.0.1:8000.');
            setLoading(false);
        }
    });

    function validateEmail(email) {
        return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email);
    }

    function setLoading(isLoading) {
        btnSubmit.disabled = isLoading;
        if (isLoading) {
            btnText.textContent = 'Authenticating...';
            btnSpinner.classList.remove('d-none');
        } else {
            btnText.textContent = 'Log In';
            btnSpinner.classList.add('d-none');
        }
    }

    function showError(msg) {
        alertErrorMessage.textContent = msg;
        alertError.style.display = 'flex';
        alertSuccess.style.display = 'none';
    }

    function showSuccess(msg) {
        alertSuccess.querySelector('span').textContent = msg;
        alertSuccess.style.display = 'flex';
        alertError.style.display = 'none';
    }

    function hideAlerts() {
        alertError.style.display = 'none';
        alertSuccess.style.display = 'none';
    }
});
