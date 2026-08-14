/**
 * IntelliBusiness - Forgot Password Controller
 */

const API_BASE_URL = 'http://127.0.0.1:8000';

document.addEventListener('DOMContentLoaded', () => {
    const forgotPasswordForm = document.getElementById('forgotPasswordForm');
    const emailInput = document.getElementById('email');
    const btnSubmit = document.getElementById('btnSubmit');
    const btnText = document.getElementById('btnText');
    const btnSpinner = document.getElementById('btnSpinner');
    const alertError = document.getElementById('alertError');
    const alertErrorMessage = document.getElementById('alertErrorMessage');
    const alertSuccess = document.getElementById('alertSuccess');

    forgotPasswordForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        hideAlerts();

        const email = emailInput.value.trim();

        if (!email || !validateEmail(email)) {
            emailInput.classList.add('is-invalid');
            return;
        } else {
            emailInput.classList.remove('is-invalid');
        }

        setLoading(true);

        try {
            const response = await fetch(`${API_BASE_URL}/api/auth/forgot-password`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ email: email })
            });

            const data = await response.json();

            if (!response.ok) {
                const errorDetail = data.detail || 'Failed to request password reset.';
                showError(errorDetail);
                setLoading(false);
                return;
            }

            showSuccess(data.message || 'Reset link sent! Please check your inbox.');
            setLoading(false);

        } catch (error) {
            console.error('Forgot Password error:', error);
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
            btnText.textContent = 'Sending...';
            btnSpinner.classList.remove('d-none');
        } else {
            btnText.textContent = 'Send Reset Link';
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
