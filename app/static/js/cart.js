/**
 * StyleSphere Cart Interactive Updates
 */

function updateCartItem(variantId, quantity) {
    const csrfToken = document.querySelector('meta[name="csrf-token"]').getAttribute('content');
    
    fetch('/cart/update', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': csrfToken
        },
        body: JSON.stringify({
            variant_id: parseInt(variantId),
            quantity: parseInt(quantity)
        })
    })
    .then(res => res.json())
    .then(data => {
        if (data.success) {
            window.location.reload();
        } else {
            alert(data.message || 'Error updating cart quantity.');
        }
    })
    .catch(err => console.error(err));
}

function removeCartItem(variantId) {
    if (!confirm('Remove this item from your shopping bag?')) return;
    const csrfToken = document.querySelector('meta[name="csrf-token"]').getAttribute('content');
    
    fetch('/cart/remove', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': csrfToken
        },
        body: JSON.stringify({ variant_id: parseInt(variantId) })
    })
    .then(res => res.json())
    .then(data => {
        if (data.success) {
            window.location.reload();
        }
    })
    .catch(err => console.error(err));
}
