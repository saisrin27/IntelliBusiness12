/**
 * IntelliBusiness - Registration Controller
 */

const API_BASE_URL = "https://intellibusiness-db.onrender.com";

document.addEventListener('DOMContentLoaded', () => {
    const registerForm = document.getElementById('registerForm');
    const fullNameInput = document.getElementById('fullName');
    const companyNameInput = document.getElementById('companyName');
    const emailInput = document.getElementById('email');
    const passwordInput = document.getElementById('password');
    const confirmPasswordInput = document.getElementById('confirmPassword');
    const agreeTermsInput = document.getElementById('agreeTerms');
    const togglePasswordBtn = document.getElementById('togglePassword');
    const togglePasswordIcon = document.getElementById('togglePasswordIcon');
    const strengthFill = document.getElementById('strengthFill');
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

    // Password Strength Dynamic Feedback
    passwordInput.addEventListener('input', () => {
        const val = passwordInput.value;
        let score = 0;
        if (val.length >= 6) score += 30;
        if (val.length >= 10) score += 20;
        if (/[A-Z]/.test(val)) score += 25;
        if (/[0-9]/.test(val)) score += 15;
        if (/[^A-Za-z0-9]/.test(val)) score += 10;

        strengthFill.style.width = `${Math.min(score, 100)}%`;
        if (score < 40) {
            strengthFill.style.backgroundColor = '#EF4444';
        } else if (score < 70) {
            strengthFill.style.backgroundColor = '#F59E0B';
        } else {
            strengthFill.style.backgroundColor = '#10B981';
        }
    });

    // Form Submission
    registerForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        hideAlerts();

        const fullName = fullNameInput.value.trim();
        const companyName = companyNameInput.value.trim();
        const email = emailInput.value.trim();
        const password = passwordInput.value;
        const confirmPassword = confirmPasswordInput.value;
        const agreeTerms = agreeTermsInput.checked;

        let isValid = true;

        if (!fullName || fullName.length < 2) {
            fullNameInput.classList.add('is-invalid');
            isValid = false;
        } else {
            fullNameInput.classList.remove('is-invalid');
        }

        if (!companyName || companyName.length < 2) {
            companyNameInput.classList.add('is-invalid');
            isValid = false;
        } else {
            companyNameInput.classList.remove('is-invalid');
        }

        if (!email || !validateEmail(email)) {
            emailInput.classList.add('is-invalid');
            isValid = false;
        } else {
            emailInput.classList.remove('is-invalid');
        }

        if (!password || password.length < 6) {
            passwordInput.classList.add('is-invalid');
            isValid = false;
        } else {
            passwordInput.classList.remove('is-invalid');
        }

        if (password !== confirmPassword) {
            confirmPasswordInput.classList.add('is-invalid');
            isValid = false;
        } else {
            confirmPasswordInput.classList.remove('is-invalid');
        }

        if (!agreeTerms) {
            agreeTermsInput.classList.add('is-invalid');
            isValid = false;
        } else {
            agreeTermsInput.classList.remove('is-invalid');
        }

        if (!isValid) return;

        setLoading(true);

        try {
            const response = await fetch(`${API_BASE_URL}/api/auth/register`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    full_name: fullName,
                    company_name: companyName,
                    email: email,
                    password: password
                })
            });

            const data = await response.json();

            if (!response.ok) {
                const errorDetail = data.detail || 'Registration failed. Please try again.';
                showError(errorDetail);
                setLoading(false);
                return;
            }

            showSuccess('Account registered successfully! Redirecting to login page...');
            
            setTimeout(() => {
                window.location.href = 'login.html';
            }, 1500);

        } catch (error) {
            console.error('Registration error:', error);
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
            btnText.textContent = 'Creating Account...';
            btnSpinner.classList.remove('d-none');
        } else {
            btnText.textContent = 'Create Account';
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
