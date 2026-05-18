/* ====== Utility Functions ====== */

/**
 * Show toast notification
 */
function showToast(message, type = 'success', duration = 3000) {
    const container = document.getElementById('toast-container');
    
    const toastEl = document.createElement('div');
    toastEl.className = `alert alert-${type} animate-slide`;
    toastEl.innerHTML = `
        <i class="fas fa-check-circle"></i>
        <span>${message}</span>
    `;
    
    container.appendChild(toastEl);
    
    setTimeout(() => {
        toastEl.classList.add('animate-fade');
        setTimeout(() => toastEl.remove(), 300);
    }, duration);
}

/**
 * Format currency
 */
function formatCurrency(amount) {
    return new Intl.NumberFormat('en-IN', {
        style: 'currency',
        currency: 'INR',
        minimumFractionDigits: 2,
    }).format(amount);
}

/**
 * Format date
 */
function formatDate(date) {
    return new Intl.DateTimeFormat('en-IN', {
        year: 'numeric',
        month: 'short',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit',
    }).format(new Date(date));
}

/**
 * Debounce function
 */
function debounce(func, delay = 300) {
    let timeoutId;
    return function (...args) {
        clearTimeout(timeoutId);
        timeoutId = setTimeout(() => func(...args), delay);
    };
}

/**
 * Throttle function
 */
function throttle(func, limit = 300) {
    let inThrottle;
    return function (...args) {
        if (!inThrottle) {
            func(...args);
            inThrottle = true;
            setTimeout(() => (inThrottle = false), limit);
        }
    };
}

/**
 * Check if element is in viewport
 */
function isInViewport(element) {
    const rect = element.getBoundingClientRect();
    return (
        rect.top >= 0 &&
        rect.left >= 0 &&
        rect.bottom <= (window.innerHeight || document.documentElement.clientHeight) &&
        rect.right <= (window.innerWidth || document.documentElement.clientWidth)
    );
}

/**
 * Smooth scroll to element
 */
function smoothScroll(elementId) {
    const element = document.getElementById(elementId);
    if (element) {
        element.scrollIntoView({ behavior: 'smooth' });
    }
}

/**
 * Clone deep object
 */
function deepClone(obj) {
    return JSON.parse(JSON.stringify(obj));
}

/**
 * Get URL parameters
 */
function getUrlParam(param) {
    const searchParams = new URLSearchParams(window.location.search);
    return searchParams.get(param);
}

/**
 * Local storage helpers
 */
const Storage = {
    set: (key, value) => localStorage.setItem(key, JSON.stringify(value)),
    get: (key) => {
        const value = localStorage.getItem(key);
        return value ? JSON.parse(value) : null;
    },
    remove: (key) => localStorage.removeItem(key),
    clear: () => localStorage.clear(),
};

/**
 * API call helper
 */
async function apiCall(endpoint, options = {}) {
    const {
        method = 'GET',
        body = null,
        headers = {},
    } = options;

    try {
        const response = await fetch(endpoint, {
            method,
            headers: {
                'Content-Type': 'application/json',
                ...headers,
            },
            body: body ? JSON.stringify(body) : null,
        });

        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }

        return await response.json();
    } catch (error) {
        console.error('API call failed:', error);
        throw error;
    }
}

/**
 * Validate email
 */
function validateEmail(email) {
    const regex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    return regex.test(email);
}

/**
 * Validate phone
 */
function validatePhone(phone) {
    const regex = /^[6-9]\d{9}$/;
    return regex.test(phone);
}

/**
 * Generate unique ID
 */
function generateId() {
    return '_' + Math.random().toString(36).substr(2, 9);
}
