/* ====== Toast Notification Handler ====== */

class ToastManager {
    constructor() {
        this.container = document.getElementById('toast-container') || this.createContainer();
    }

    createContainer() {
        const container = document.createElement('div');
        container.id = 'toast-container';
        container.className = 'fixed bottom-4 right-4 z-50 space-y-2';
        document.body.appendChild(container);
        return container;
    }

    show(message, type = 'success', duration = 3000) {
        const toastId = generateId();
        const toast = document.createElement('div');
        toast.id = toastId;
        toast.className = `alert alert-${type}`;
        
        let icon = '✓';
        if (type === 'error' || type === 'danger') icon = '✕';
        if (type === 'warning') icon = '⚠';
        if (type === 'info') icon = 'ℹ';
        
        toast.innerHTML = `
            <div class="alert-icon">${icon}</div>
            <div class="alert-content">
                <div class="alert-message">${message}</div>
            </div>
            <button class="alert-close" onclick="this.closest('.alert').classList.add('dismissing'); setTimeout(() => this.closest('.alert').remove(), 300);">
                ✕
            </button>
        `;
        
        this.container.appendChild(toast);
        
        if (duration > 0) {
            setTimeout(() => {
                if (toast.parentNode) {
                    toast.remove();
                }
            }, duration);
        }
        
        return toastId;
    }

    success(message, duration) {
        return this.show(message, 'success', duration);
    }

    error(message, duration) {
        return this.show(message, 'danger', duration);
    }

    warning(message, duration) {
        return this.show(message, 'warning', duration);
    }

    info(message, duration) {
        return this.show(message, 'info', duration);
    }
}

// Initialize global toast manager
const toast = new ToastManager();
