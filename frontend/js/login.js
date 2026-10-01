/**
 * IntelliBusiness - Login Controller
 */

const API_BASE_URL = window.INTELLIBUSINESS_API_BASE_URL || (
    ["localhost", "127.0.0.1"].includes(window.location.hostname)
        ? "http://127.0.0.1:8000"
        : "https://intellibusiness-db.onrender.com"
);

document.addEventListener('DOMContentLoaded', async () => {
    const googleButton = document.getElementById('googleSignInButton');
    if (googleButton) googleButton.href = `${API_BASE_URL}/api/auth/google`;
    const googleError = new URLSearchParams(window.location.search).get('google_error');
    const registrationComplete = new URLSearchParams(window.location.search).get('registered');

    // Redirect to dashboard if already logged in
    const existingToken = localStorage.getItem('access_token');
    if (existingToken && !googleError && !registrationComplete) {
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
    const resendVerificationPanel = document.getElementById('resendVerificationPanel');
    const resendVerificationButton = document.getElementById('resendVerificationButton');

    const googleErrorMessages = {
        cancelled: 'Google sign-in was cancelled.',
        state: 'Google sign-in could not be verified. Please try again.',
        unverified: 'Google did not confirm a verified email address.',
        verification_required: 'Verify your existing account email before using Google sign-in.',
        account_conflict: 'This Google account is linked to a different IntelliBusiness account.',
        failed: 'Google sign-in failed. Please try again.',
    };
    if (googleError) {
        console.error('Google OAuth error reported by backend:', googleError);
        showError(googleErrorMessages[googleError] || googleErrorMessages.failed);
    }
    if (registrationComplete) showSuccess('Account created. Check your email for the verification link before signing in.');
    if (googleError || registrationComplete) {
        window.history.replaceState({}, document.title, window.location.pathname);
    }

    resendVerificationButton?.addEventListener('click', async () => {
        const email = emailInput.value.trim();
        if (!validateEmail(email)) {
            emailInput.classList.add('is-invalid');
            return;
        }
        resendVerificationButton.disabled = true;
        try {
            const response = await fetch(`${API_BASE_URL}/api/auth/resend-verification`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ email }),
            });
            const data = await response.json();
            if (!response.ok) throw new Error(data.detail || 'Unable to resend the verification email.');
            showSuccess(data.message);
        } catch (error) {
            showError(error.message);
        } finally {
            resendVerificationButton.disabled = false;
        }
    });

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
                if (response.status === 403) resendVerificationPanel?.classList.remove('d-none');
                setLoading(false);
                return;
            }

            // Store Token & User details
            localStorage.setItem('access_token', data.access_token);
            localStorage.setItem('user', JSON.stringify(data.user));

            showSuccess('Login successful! Redirecting to your dashboard...');

            setTimeout(() => {
                const role = data.user?.role || 'user';

                if (role.toLowerCase() === 'admin') {
                window.location.href = 'admin-dashboard.html';
                } else {
                window.location.href = 'dashboard.html';
                }
            }, 1000);

        } catch (error) {
            console.error('Login error:', error);
            showError('Unable to connect to the server. Please try again.');
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
