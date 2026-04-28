document.addEventListener('DOMContentLoaded', () => {
    const typeRadios = document.querySelectorAll('input[name="property_type_toggle"]');
    const chungCuFields = document.querySelectorAll('.chung-cu-only');
    const nhaDatFields = document.querySelectorAll('.nha-dat-only');
    const form = document.getElementById('prediction-form');
    const resultContainer = document.getElementById('result-container');
    const predictedPriceEl = document.getElementById('predicted-price');
    const resultMessageEl = document.getElementById('result-message');
    const errorEl = document.getElementById('error-message');
    const submitBtn = document.getElementById('submit-btn');
    const btnText = submitBtn.querySelector('.btn-text');
    const spinner = submitBtn.querySelector('.spinner');
    const resetBtn = document.getElementById('reset-btn');

    // Toggle fields based on property type
    function updateFields() {
        const isNhaDat = document.getElementById('type-nha-dat').checked;
        
        if (isNhaDat) {
            chungCuFields.forEach(el => {
                el.style.display = 'none';
                const input = el.querySelector('input, select');
                if(input) input.required = false;
            });
            nhaDatFields.forEach(el => {
                el.style.display = 'block';
                const input = el.querySelector('input, select');
                if(input) input.required = true;
            });
        } else {
            chungCuFields.forEach(el => {
                el.style.display = 'block';
                const input = el.querySelector('input, select');
                if(input) input.required = true;
            });
            nhaDatFields.forEach(el => {
                el.style.display = 'none';
                const input = el.querySelector('input, select');
                if(input) input.required = false;
            });
        }
    }

    typeRadios.forEach(radio => {
        radio.addEventListener('change', updateFields);
    });

    // Initial setup
    updateFields();

    // Format currency
    function formatCurrency(value) {
        if (value >= 1000000000) {
            return (value / 1000000000).toFixed(2) + ' Tỷ VNĐ';
        } else {
            return (value / 1000000).toFixed(0) + ' Triệu VNĐ';
        }
    }

    // Animate number count up
    function animateValue(obj, start, end, duration) {
        let startTimestamp = null;
        const step = (timestamp) => {
            if (!startTimestamp) startTimestamp = timestamp;
            const progress = Math.min((timestamp - startTimestamp) / duration, 1);
            // easeOutQuart
            const easeProgress = 1 - Math.pow(1 - progress, 4);
            const currentVal = Math.floor(easeProgress * (end - start) + start);
            obj.innerHTML = formatCurrency(currentVal);
            if (progress < 1) {
                window.requestAnimationFrame(step);
            } else {
                obj.innerHTML = formatCurrency(end);
            }
        };
        window.requestAnimationFrame(step);
    }

    // Form submission
    form.addEventListener('submit', async (e) => {
        e.preventDefault();
        errorEl.textContent = '';
        
        // UI Loading state
        btnText.style.display = 'none';
        spinner.style.display = 'block';
        submitBtn.disabled = true;

        const formData = new FormData(form);
        const data = Object.fromEntries(formData.entries());
        data.property_type = document.getElementById('type-nha-dat').checked ? 'nha_dat' : 'chung_cu';

        try {
            const response = await fetch('/predict', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(data)
            });

            const result = await response.json();

            if (result.success) {
                // Hide form, show result
                form.style.display = 'none';
                resultContainer.classList.remove('hidden');
                
                // Animate price
                const finalPrice = result.predicted_price_vnd;
                animateValue(predictedPriceEl, 0, finalPrice, 2000);
                
                resultMessageEl.textContent = result.message;

                // Render similar properties
                const similarContainer = document.getElementById('similar-properties-container');
                const similarList = document.getElementById('similar-list');
                similarList.innerHTML = ''; // Clear old

                if (result.similar_properties && result.similar_properties.length > 0) {
                    similarContainer.classList.remove('hidden');
                    result.similar_properties.forEach(prop => {
                        const card = document.createElement('a');
                        const type = prop.property_type === 'nha_dat' ? 'nha_dat' : 'chung_cu';
                        const id = Number.isInteger(Number(prop.id)) ? Number(prop.id) : 0;
                        const image = safeImageUrl(prop.image);
                        const title = escapeHtml(prop.title || prop.district || '');
                        const district = escapeHtml(prop.district || '');
                        const price = Number.isFinite(Number(prop.price_billion)) ? Number(prop.price_billion) : 0;
                        const area = Number.isFinite(Number(prop.area_m2)) ? Number(prop.area_m2) : 0;
                        const desc = escapeHtml(prop.desc || '');
                        card.href = `/property/${type}/${id}`;
                        card.className = 'similar-card';

                        const imgHtml = image
                            ? `<img class="card-thumbnail" src="${image}" alt="${district}" loading="lazy" onerror="this.style.display='none';this.nextElementSibling.style.display='flex'"><div class="card-thumbnail-placeholder" style="display:none">🏠</div>`
                            : `<div class="card-thumbnail-placeholder">🏠</div>`;

                        card.innerHTML = `
                            ${imgHtml}
                            <div class="card-body">
                                <p class="card-title">${title}</p>
                                <p class="card-price">${price} Tỷ VNĐ</p>
                                <div class="card-meta">
                                    <span>📐 ${area} m²</span>
                                    <span>📍 ${district}</span>
                                </div>
                                <p class="card-meta">${desc}</p>
                            </div>
                        `;
                        similarList.appendChild(card);
                    });
                } else {
                    similarContainer.classList.add('hidden');
                }
            } else {
                errorEl.textContent = result.error || 'Có lỗi xảy ra khi dự đoán.';
            }
        } catch (error) {
            errorEl.textContent = 'Không thể kết nối tới server.';
            console.error(error);
        } finally {
            // Restore UI state
            btnText.style.display = 'block';
            spinner.style.display = 'none';
            submitBtn.disabled = false;
        }
    });

    // Reset button
    resetBtn.addEventListener('click', () => {
        resultContainer.classList.add('hidden');
        form.style.display = 'block';
        form.reset();
        errorEl.textContent = '';
        updateFields();
    });

    // Smooth page transitions
    document.addEventListener('click', (e) => {
        const link = e.target.closest('a');
        if (link && link.href && link.target !== '_blank' && !link.href.startsWith('#') && !link.href.startsWith('javascript:')) {
            e.preventDefault();
            document.body.classList.add('page-transitioning');
            setTimeout(() => {
                window.location.href = link.href;
            }, 250);
        }
    });
});

function escapeHtml(value) {
    return String(value).replace(/[&<>"']/g, ch => ({
        '&': '&amp;',
        '<': '&lt;',
        '>': '&gt;',
        '"': '&quot;',
        "'": '&#39;'
    }[ch]));
}

function safeImageUrl(value) {
    const url = String(value || '').trim();
    return /^https?:\/\//i.test(url) ? escapeHtml(url) : '';
}
