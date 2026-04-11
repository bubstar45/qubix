// Auto-hide messages
document.addEventListener('DOMContentLoaded', function() {
    const messages = document.querySelectorAll('.alert');
    messages.forEach(message => {
        setTimeout(() => {
            message.style.opacity = '0';
            setTimeout(() => message.remove(), 300);
        }, 5000);
    });
});

// Format currency
function formatCurrency(amount) {
    return new Intl.NumberFormat('en-US', {
        style: 'currency',
        currency: 'USD'
    }).format(amount);
}

// Format number with commas
function formatNumber(number) {
    return new Intl.NumberFormat('en-US').format(number);
}

// Show loading state
function showLoading(button) {
    const originalText = button.textContent;
    button.disabled = true;
    button.innerHTML = '<div class="spinner"></div>';
    return originalText;
}

// Hide loading state
function hideLoading(button, originalText) {
    button.disabled = false;
    button.textContent = originalText;
}