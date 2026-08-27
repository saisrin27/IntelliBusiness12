const API_BASE_URL = 'http://127.0.0.1:8000';
const GENERIC_RESET_MESSAGE = 'If an account exists with this email, a reset code has been sent.';

document.addEventListener('DOMContentLoaded', () => {
    const emailStep = document.getElementById('emailStep');
    const otpStep = document.getElementById('otpStep');
    const passwordStep = document.getElementById('passwordStep');
    const emailInput = document.getElementById('email');
    const otpInput = document.getElementById('otp');
    const forgotForm = document.getElementById('forgotPasswordForm');
    const otpForm = document.getElementById('otpForm');
    const resetForm = document.getElementById('resetPasswordForm');
    const resendBtn = document.getElementById('resendBtn');
    const countdown = document.getElementById('countdown');
    const alertError = document.getElementById('alertError');
    const alertErrorMessage = document.getElementById('alertErrorMessage');
    const alertSuccess = document.getElementById('alertSuccess');
    const alertSuccessMessage = document.getElementById('alertSuccessMessage');
    let resetToken = '';
    let countdownTimer;
    let resendTimer;

    forgotForm.addEventListener('submit', (event) => requestCode(event, '/api/auth/forgot-password'));
    resendBtn.addEventListener('click', () => requestCode(null, '/api/auth/resend-otp'));
    otpForm.addEventListener('submit', verifyCode);
    resetForm.addEventListener('submit', resetPassword);

    async function requestCode(event, endpoint) {
        event?.preventDefault();
        hideAlerts();
        const email = emailInput.value.trim();
        if (!validateEmail(email)) {
            emailInput.classList.add('is-invalid');
            return;
        }
        emailInput.classList.remove('is-invalid');
        setButtonLoading('btnSubmit', true, 'Sending...');
        try {
            const response = await fetch(`${API_BASE_URL}${endpoint}`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ email }),
            });
            const data = await response.json();
            if (!response.ok) throw new Error(data.detail || 'Unable to request a reset code.');
            showSuccess(data.message || GENERIC_RESET_MESSAGE);
            emailStep.classList.add('d-none');
            otpStep.classList.remove('d-none');
            otpStep.style.display = 'block';
            document.getElementById('resetSubtitle').textContent = 'Enter the 6-digit code sent to your email';
            startCountdown(600);
            startResendCooldown(60);
        } catch (error) {
            showError(error.message);
        } finally {
            setButtonLoading('btnSubmit', false, 'Send Reset Code');
        }
    }

    async function verifyCode(event) {
        event.preventDefault();
        hideAlerts();
        const otp = otpInput.value.trim();
        if (!/^\d{6}$/.test(otp)) {
            otpInput.classList.add('is-invalid');
            return;
        }
        otpInput.classList.remove('is-invalid');
        setButtonLoading('verifyBtn', true, 'Verifying...');
        try {
            const response = await fetch(`${API_BASE_URL}/api/auth/verify-reset-otp`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ email: emailInput.value.trim(), otp }),
            });
            const data = await response.json();
            if (!response.ok) throw new Error(data.detail || 'Invalid or expired reset code.');
            resetToken = data.reset_token;
            clearInterval(countdownTimer);
            otpStep.classList.add('d-none');
            passwordStep.classList.remove('d-none');
            document.getElementById('resetSubtitle').textContent = 'Create a new password for your account';
            showSuccess(data.message);
        } catch (error) {
            showError(error.message);
        } finally {
            setButtonLoading('verifyBtn', false, 'Verify Code');
        }
    }

    async function resetPassword(event) {
        event.preventDefault();
        hideAlerts();
        const newPassword = document.getElementById('newPassword').value;
        const confirmPassword = document.getElementById('confirmPassword').value;
        if (newPassword.length < 6) return showError('Password must be at least 6 characters long.');
        if (newPassword !== confirmPassword) return showError('New passwords do not match.');
        setButtonLoading('resetBtn', true, 'Resetting...');
        try {
            const response = await fetch(`${API_BASE_URL}/api/auth/reset-password`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ reset_token: resetToken, new_password: newPassword, confirm_password: confirmPassword }),
            });
            const data = await response.json();
            if (!response.ok) throw new Error(data.detail || 'Unable to reset password.');
            showSuccess(data.message);
            resetForm.reset();
            setTimeout(() => { window.location.href = 'login.html'; }, 1500);
        } catch (error) {
            showError(error.message);
        } finally {
            setButtonLoading('resetBtn', false, 'Reset Password');
        }
    }

    function startCountdown(seconds) {
        clearInterval(countdownTimer);
        const update = () => {
            const minutes = Math.floor(seconds / 60);
            countdown.textContent = `${minutes}:${String(seconds % 60).padStart(2, '0')}`;
            if (seconds <= 0) clearInterval(countdownTimer);
            seconds -= 1;
        };
        update();
        countdownTimer = setInterval(update, 1000);
    }

    function startResendCooldown(seconds) {
        clearInterval(resendTimer);
        resendBtn.disabled = true;
        resendBtn.textContent = `Resend code in ${seconds}s`;
        resendTimer = setInterval(() => {
            seconds -= 1;
            if (seconds <= 0) {
                clearInterval(resendTimer);
                resendBtn.disabled = false;
                resendBtn.textContent = 'Resend code';
            } else {
                resendBtn.textContent = `Resend code in ${seconds}s`;
            }
        }, 1000);
    }

    function setButtonLoading(id, loading, label) {
        const button = document.getElementById(id);
        if (!button) return;
        button.disabled = loading;
        button.querySelector('span').textContent = label;
        button.querySelector('.spinner-border')?.classList.toggle('d-none', !loading);
    }

    function validateEmail(email) { return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email); }
    function showError(message) { alertErrorMessage.textContent = message; alertError.style.display = 'flex'; alertSuccess.style.display = 'none'; }
    function showSuccess(message) { alertSuccessMessage.textContent = message; alertSuccess.style.display = 'flex'; alertError.style.display = 'none'; }
    function hideAlerts() { alertError.style.display = 'none'; alertSuccess.style.display = 'none'; }
});
