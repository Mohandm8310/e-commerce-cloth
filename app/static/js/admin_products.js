/**
 * StyleSphere Admin Product Management with Reversible Soft-Delete & 30-Second Undo
 */

document.addEventListener('DOMContentLoaded', function () {
    const container = document.getElementById('undo-toast-container') || createUndoContainer();

    document.querySelectorAll('.btn-delete-product').forEach(btn => {
        btn.addEventListener('click', function (e) {
            e.preventDefault();
            const productId = this.dataset.productId;
            const productName = this.dataset.productName;
            const row = document.getElementById(`product-row-${productId}`);

            if (!confirm(`Are you sure you want to delete product "${productName}"? You can undo this within 30 seconds.`)) {
                return;
            }

            const csrfToken = document.querySelector('meta[name="csrf-token"]').getAttribute('content');

            fetch(`/admin/products/${productId}/delete`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': csrfToken,
                    'X-Requested-With': 'XMLHttpRequest'
                }
            })
            .then(res => res.json())
            .then(data => {
                if (data.success) {
                    if (row) {
                        row.style.transition = 'opacity 0.4s ease';
                        row.style.opacity = '0.25';
                        row.classList.add('table-danger');
                    }
                    showUndoToast(productId, productName, data.undo_url, data.undo_seconds || 30);
                } else {
                    alert(data.message || 'Error deleting product.');
                }
            })
            .catch(err => console.error('Delete error:', err));
        });
    });

    function createUndoContainer() {
        const div = document.createElement('div');
        div.id = 'undo-toast-container';
        document.body.appendChild(div);
        return div;
    }

    function showUndoToast(productId, productName, undoUrl, seconds) {
        const toast = document.createElement('div');
        toast.className = 'undo-toast shadow-lg mb-2';
        toast.id = `undo-toast-${productId}`;

        toast.innerHTML = `
            <div class="undo-toast-header">
                <div class="d-flex align-items-center gap-2">
                    <i class="bi bi-trash3 text-danger fs-5"></i>
                    <div>
                        <div class="fw-semibold small">Product deleted</div>
                        <div class="text-white-50 small text-truncate" style="max-width: 200px;">"${productName}"</div>
                    </div>
                </div>
                <button type="button" class="btn btn-primary btn-sm px-3 fw-bold btn-undo-action" data-product-id="${productId}">
                    Undo (<span class="undo-timer">${seconds}</span>s)
                </button>
            </div>
            <div class="undo-progress-bar" style="width: 100%;"></div>
        `;

        container.appendChild(toast);

        let remaining = seconds;
        const timerSpan = toast.querySelector('.undo-timer');
        const progressBar = toast.querySelector('.undo-progress-bar');
        progressBar.style.transition = `width ${seconds}s linear`;
        setTimeout(() => progressBar.style.width = '0%', 50);

        const interval = setInterval(() => {
            remaining -= 1;
            if (timerSpan) timerSpan.textContent = remaining;
            if (remaining <= 0) {
                clearInterval(interval);
                toast.remove();
                const row = document.getElementById(`product-row-${productId}`);
                if (row) row.remove();
            }
        }, 1000);

        // Undo click handler
        toast.querySelector('.btn-undo-action').addEventListener('click', function () {
            clearInterval(interval);
            const csrfToken = document.querySelector('meta[name="csrf-token"]').getAttribute('content');

            fetch(undoUrl, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': csrfToken,
                    'X-Requested-With': 'XMLHttpRequest'
                }
            })
            .then(res => res.json())
            .then(resData => {
                if (resData.success) {
                    toast.remove();
                    const row = document.getElementById(`product-row-${productId}`);
                    if (row) {
                        row.style.opacity = '1';
                        row.classList.remove('table-danger');
                        row.classList.add('table-success');
                        setTimeout(() => row.classList.remove('table-success'), 2500);
                    }
                } else {
                    alert(resData.message || 'Error restoring product.');
                }
            })
            .catch(err => console.error('Restore error:', err));
        });
    }
});
