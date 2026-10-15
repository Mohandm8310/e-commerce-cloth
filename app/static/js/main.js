/**
 * StyleSphere Storefront Interactive JavaScript
 */

document.addEventListener('DOMContentLoaded', function () {
    // 1. Wishlist Toggle buttons
    document.querySelectorAll('.btn-wishlist-toggle').forEach(button => {
        button.addEventListener('click', function (e) {
            e.preventDefault();
            const productId = this.dataset.productId;
            const csrfToken = document.querySelector('meta[name="csrf-token"]').getAttribute('content');
            const icon = this.querySelector('i');

            fetch('/customer/wishlist/toggle', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': csrfToken
                },
                body: JSON.stringify({ product_id: parseInt(productId) })
            })
            .then(res => {
                if (res.status === 401 || res.redirected) {
                    window.location.href = '/auth/login?next=' + encodeURIComponent(window.location.pathname);
                    return;
                }
                return res.json();
            })
            .then(data => {
                if (!data) return;
                if (data.success) {
                    if (data.in_wishlist) {
                        icon.classList.remove('bi-heart');
                        icon.classList.add('bi-heart-fill', 'text-danger');
                    } else {
                        icon.classList.remove('bi-heart-fill', 'text-danger');
                        icon.classList.add('bi-heart');
                    }
                }
            })
            .catch(err => console.error('Wishlist error:', err));
        });
    });

    // 2. OTP 6-Digit Box Auto-Focus & Paste Stepper
    const otpBoxes = document.querySelectorAll('.otp-box');
    const hiddenOtpInput = document.getElementById('otp-code-hidden');

    if (otpBoxes.length > 0) {
        otpBoxes[0].focus();

        otpBoxes.forEach((box, index) => {
            box.addEventListener('input', function (e) {
                const val = this.value.replace(/\D/g, '');
                this.value = val ? val[0] : '';

                if (this.value && index < otpBoxes.length - 1) {
                    otpBoxes[index + 1].focus();
                }
                syncOtpCode();
            });

            box.addEventListener('keydown', function (e) {
                if (e.key === 'Backspace' && !this.value && index > 0) {
                    otpBoxes[index - 1].focus();
                }
            });

            box.addEventListener('paste', function (e) {
                e.preventDefault();
                const pastedData = (e.clipboardData || window.clipboardData).getData('text').trim();
                const digits = pastedData.replace(/\D/g, '').slice(0, 6);
                digits.split('').forEach((digit, i) => {
                    if (otpBoxes[i]) {
                        otpBoxes[i].value = digit;
                    }
                });
                syncOtpCode();
                if (digits.length >= otpBoxes.length) {
                    otpBoxes[otpBoxes.length - 1].focus();
                } else if (otpBoxes[digits.length]) {
                    otpBoxes[digits.length].focus();
                }
            });
        });

        function syncOtpCode() {
            let code = '';
            otpBoxes.forEach(b => code += b.value);
            if (hiddenOtpInput) {
                hiddenOtpInput.value = code;
            }
        }
    }
});
