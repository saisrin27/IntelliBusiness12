/**
 * IntelliBusiness - Landing Page JavaScript
 * Handles interactions, animations, and user engagement
 */

// ============================================
// LOADING SCREEN
// ============================================

/**
 * Hide loading screen when page is fully loaded
 */
document.addEventListener('DOMContentLoaded', function () {
    const loadingScreen = document.getElementById('loadingScreen');
    
    // Hide loading screen after a minimum of 1 second
    setTimeout(() => {
        if (loadingScreen) {
            loadingScreen.classList.add('hidden');
        }
    }, 1000);
    
    // Initialize all features
    initializeScrollAnimations();
    initializeNavbarHighlight();
    initializeBackToTop();
    initializeDarkMode();
    initializeContactForm();
    initializeSmoothScroll();
});

// ============================================
// DARK MODE TOGGLE
// ============================================

/**
 * Initialize dark mode functionality
 */
function initializeDarkMode() {
    const darkModeToggle = document.getElementById('darkModeToggle');
    const htmlElement = document.documentElement;
    const body = document.body;
    
    // Check for saved dark mode preference
    const isDarkMode = localStorage.getItem('darkMode') === 'true';
    
    if (isDarkMode) {
        enableDarkMode();
    }
    
    // Dark mode toggle click handler
    if (darkModeToggle) {
        darkModeToggle.addEventListener('click', function () {
            if (body.classList.contains('dark-mode')) {
                disableDarkMode();
            } else {
                enableDarkMode();
            }
        });
    }
    
    // Function to enable dark mode
    function enableDarkMode() {
        body.classList.add('dark-mode');
        localStorage.setItem('darkMode', 'true');
        if (darkModeToggle) {
            darkModeToggle.innerHTML = '<i class="fas fa-sun"></i>';
            darkModeToggle.title = 'Toggle Light Mode';
        }
    }
    
    // Function to disable dark mode
    function disableDarkMode() {
        body.classList.remove('dark-mode');
        localStorage.setItem('darkMode', 'false');
        if (darkModeToggle) {
            darkModeToggle.innerHTML = '<i class="fas fa-moon"></i>';
            darkModeToggle.title = 'Toggle Dark Mode';
        }
    }
}

// ============================================
// SMOOTH SCROLLING
// ============================================

/**
 * Initialize smooth scrolling for navigation links
 */
function initializeSmoothScroll() {
    // Get all navigation links
    const navLinks = document.querySelectorAll('a[href^="#"]');
    
    navLinks.forEach(link => {
        link.addEventListener('click', function (e) {
            const href = this.getAttribute('href');
            
            // Skip if href is just "#"
            if (href === '#') {
                e.preventDefault();
                return;
            }
            
            const targetElement = document.querySelector(href);
            
            if (targetElement) {
                e.preventDefault();
                
                // Close mobile menu if open
                const navbarToggle = document.querySelector('.navbar-toggler');
                const navbarCollapse = document.querySelector('.navbar-collapse');
                if (navbarCollapse && navbarCollapse.classList.contains('show')) {
                    navbarToggle.click();
                }
                
                // Smooth scroll to target
                const offsetTop = targetElement.offsetTop - 80; // Account for sticky navbar
                window.scrollTo({
                    top: offsetTop,
                    behavior: 'smooth'
                });
            }
        });
    });
}

// ============================================
// NAVBAR ACTIVE SECTION HIGHLIGHT
// ============================================

/**
 * Update active navbar link based on scroll position
 */
function initializeNavbarHighlight() {
    const navLinks = document.querySelectorAll('.nav-link-custom');
    
    window.addEventListener('scroll', function () {
        let current = '';
        
        // Check which section is currently visible
        const sections = document.querySelectorAll('section[id]');
        sections.forEach(section => {
            const sectionTop = section.offsetTop;
            const sectionHeight = section.clientHeight;
            if (pageYOffset >= sectionTop - 200) {
                current = section.getAttribute('id');
            }
        });
        
        // Update active link
        navLinks.forEach(link => {
            link.classList.remove('active');
            if (link.getAttribute('href') === '#' + current) {
                link.classList.add('active');
            }
        });
    });
}

// ============================================
// BACK TO TOP BUTTON
// ============================================

/**
 * Initialize back to top button functionality
 */
function initializeBackToTop() {
    const backToTopBtn = document.getElementById('backToTopBtn');
    
    // Show/hide back to top button based on scroll
    window.addEventListener('scroll', function () {
        if (window.pageYOffset > 300) {
            backToTopBtn.classList.add('visible');
        } else {
            backToTopBtn.classList.remove('visible');
        }
    });
    
    // Scroll to top when button is clicked
    if (backToTopBtn) {
        backToTopBtn.addEventListener('click', function () {
            window.scrollTo({
                top: 0,
                behavior: 'smooth'
            });
        });
    }
}

// ============================================
// SCROLL ANIMATIONS
// ============================================

/**
 * Initialize scroll animation for elements
 */
function initializeScrollAnimations() {
    const elements = document.querySelectorAll('.feature-card, .benefit-card, .testimonial-card, .pricing-card, .accordion-item');
    
    // Create Intersection Observer
    const observer = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                entry.target.classList.add('scroll-animation', 'visible');
                observer.unobserve(entry.target);
            }
        });
    }, {
        threshold: 0.1,
        rootMargin: '0px 0px -100px 0px'
    });
    
    // Observe all elements
    elements.forEach(element => {
        element.classList.add('scroll-animation');
        observer.observe(element);
    });
}

// ============================================
// CONTACT FORM VALIDATION
// ============================================

/**
 * Initialize contact form validation and submission
 */
function initializeContactForm() {
    const contactForm = document.getElementById('contactForm');
    
    if (contactForm) {
        contactForm.addEventListener('submit', function (e) {
            e.preventDefault();
            
            // Get form fields
            const name = document.getElementById('name');
            const email = document.getElementById('email');
            const company = document.getElementById('company');
            const phone = document.getElementById('phone');
            const message = document.getElementById('message');
            
            // Validate form
            let isValid = true;
            
            // Reset error messages
            document.querySelectorAll('.error-message').forEach(msg => msg.textContent = '');
            document.querySelectorAll('.form-control').forEach(input => input.classList.remove('is-invalid'));
            
            // Validate name
            if (!name.value.trim()) {
                showError(name, 'Name is required');
                isValid = false;
            }
            
            // Validate email
            if (!email.value.trim()) {
                showError(email, 'Email is required');
                isValid = false;
            } else if (!isValidEmail(email.value)) {
                showError(email, 'Please enter a valid email');
                isValid = false;
            }
            
            // Validate company
            if (!company.value.trim()) {
                showError(company, 'Company is required');
                isValid = false;
            }
            
            // Validate message
            if (!message.value.trim()) {
                showError(message, 'Message is required');
                isValid = false;
            } else if (message.value.trim().length < 10) {
                showError(message, 'Message must be at least 10 characters');
                isValid = false;
            }
            
            // If form is valid, show success message
            if (isValid) {
                // Prepare form data
                const formData = {
                    name: name.value.trim(),
                    email: email.value.trim(),
                    company: company.value.trim(),
                    phone: phone.value.trim(),
                    message: message.value.trim(),
                    timestamp: new Date().toISOString()
                };
                
                // Store in localStorage (simulate backend)
                let submissions = JSON.parse(localStorage.getItem('contactFormSubmissions')) || [];
                submissions.push(formData);
                localStorage.setItem('contactFormSubmissions', JSON.stringify(submissions));
                
                // Show success message
                showSuccessMessage();
                
                // Reset form
                contactForm.reset();
                
                // Hide success message after 5 seconds
                setTimeout(() => {
                    hideSuccessMessage();
                }, 5000);
            }
        });
    }
}

/**
 * Show error message for form field
 */
function showError(field, message) {
    field.classList.add('is-invalid');
    const errorElement = field.parentElement.querySelector('.error-message');
    if (errorElement) {
        errorElement.textContent = message;
    }
}

/**
 * Show success message
 */
function showSuccessMessage() {
    const successDiv = document.querySelector('.success-message');
    if (successDiv) {
        successDiv.style.display = 'flex';
    }
}

/**
 * Hide success message
 */
function hideSuccessMessage() {
    const successDiv = document.querySelector('.success-message');
    if (successDiv) {
        successDiv.style.display = 'none';
    }
}

/**
 * Validate email format
 */
function isValidEmail(email) {
    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    return emailRegex.test(email);
}

// ============================================
// FEATURE CARD HOVER EFFECTS
// ============================================

/**
 * Add hover effects to feature cards
 */
document.addEventListener('DOMContentLoaded', function () {
    const featureCards = document.querySelectorAll('.feature-card');
    
    featureCards.forEach(card => {
        card.addEventListener('mouseenter', function () {
            this.style.transform = 'translateY(-10px) scale(1.02)';
        });
        
        card.addEventListener('mouseleave', function () {
            this.style.transform = 'translateY(0) scale(1)';
        });
    });
});

// ============================================
// LEARN MORE BUTTON
// ============================================

/**
 * Handle "Learn More" button click
 */
document.addEventListener('DOMContentLoaded', function () {
    const learnMoreBtn = document.getElementById('learnMoreBtn');
    
    if (learnMoreBtn) {
        learnMoreBtn.addEventListener('click', function () {
            const featuresSection = document.getElementById('features');
            if (featuresSection) {
                featuresSection.scrollIntoView({ behavior: 'smooth' });
            }
        });
    }
});

// ============================================
// MOBILE RESPONSIVE ENHANCEMENTS
// ============================================

/**
 * Close mobile menu when link is clicked
 */
document.addEventListener('DOMContentLoaded', function () {
    const navbarToggler = document.querySelector('.navbar-toggler');
    const navbarCollapse = document.querySelector('.navbar-collapse');
    const navLinks = document.querySelectorAll('.navbar-collapse .nav-link');
    
    navLinks.forEach(link => {
        link.addEventListener('click', function () {
            if (navbarCollapse.classList.contains('show')) {
                navbarToggler.click();
            }
        });
    });
});

// ============================================
// WINDOW RESIZE HANDLER
// ============================================

/**
 * Handle window resize events
 */
let resizeTimer;
window.addEventListener('resize', function () {
    clearTimeout(resizeTimer);
    resizeTimer = setTimeout(function () {
        // Recalculate animations on resize
        initializeScrollAnimations();
    }, 250);
});

// ============================================
// PERFORMANCE OPTIMIZATIONS
// ============================================

/**
 * Lazy load images (if added in future)
 */
if ('IntersectionObserver' in window) {
    const imageObserver = new IntersectionObserver((entries, observer) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                const img = entry.target;
                img.src = img.dataset.src || img.src;
                img.classList.remove('lazy');
                imageObserver.unobserve(img);
            }
        });
    });
    
    document.querySelectorAll('img.lazy').forEach(img => imageObserver.observe(img));
}

// ============================================
// ACCESSIBILITY ENHANCEMENTS
// ============================================

/**
 * Keyboard navigation support
 */
document.addEventListener('keydown', function (e) {
    // Escape key to close mobile menu
    if (e.key === 'Escape') {
        const navbarCollapse = document.querySelector('.navbar-collapse');
        const navbarToggler = document.querySelector('.navbar-toggler');
        if (navbarCollapse.classList.contains('show')) {
            navbarToggler.click();
        }
    }
});

// ============================================
// PREFERS REDUCED MOTION
// ============================================

/**
 * Respect user's motion preferences
 */
if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
    document.documentElement.style.scrollBehavior = 'auto';
    const style = document.createElement('style');
    style.textContent = `
        * {
            animation-duration: 0.01ms !important;
            animation-iteration-count: 1 !important;
            transition-duration: 0.01ms !important;
        }
    `;
    document.head.appendChild(style);
}

// ============================================
// CONSOLE LOG FOR DEBUGGING (OPTIONAL)
// ============================================

console.log('%cIntelliBusiness Landing Page', 'color: #2563EB; font-size: 18px; font-weight: bold;');
console.log('%cBuilt with HTML5, CSS3, and Vanilla JavaScript', 'color: #7C3AED; font-size: 12px;');
console.log('%cFeatures: Dark Mode, Smooth Scrolling, Form Validation, Animations', 'color: #2563EB; font-size: 11px;');
