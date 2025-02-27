/**
 * DMM X自動投稿システム共通JavaScript
 */

document.addEventListener('DOMContentLoaded', function() {
    // アラートを自動で閉じる
    const alerts = document.querySelectorAll('.alert:not(.alert-permanent)');
    alerts.forEach(alert => {
        setTimeout(() => {
            const closeButton = alert.querySelector('.btn-close');
            if (closeButton) {
                closeButton.click();
            } else {
                alert.style.display = 'none';
            }
        }, 5000);
    });
    
    // 画像サムネイルクリックでチェックボックスをトグル
    const imageCards = document.querySelectorAll('.image-card');
    imageCards.forEach(card => {
        const checkbox = card.querySelector('input[type="checkbox"]');
        if (checkbox) {
            // カード全体をクリックでチェックボックス切り替え（ただしチェックボックス自体を除く）
            card.addEventListener('click', function(e) {
                // チェックボックス自体やそのラベルをクリックした場合は処理しない
                if (e.target !== checkbox && e.target.tagName !== 'LABEL') {
                    checkbox.checked = !checkbox.checked;
                    
                    // changeイベントを発火
                    const changeEvent = new Event('change', { bubbles: true });
                    checkbox.dispatchEvent(changeEvent);
                }
            });
        }
    });
    
    // Tooltips初期化
    var tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    var tooltipList = tooltipTriggerList.map(function (tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl);
    });
    
    // 日付ピッカー（もし使用する場合）
    const datePickers = document.querySelectorAll('.datepicker');
    if (datePickers.length > 0) {
        datePickers.forEach(el => {
            if (typeof flatpickr !== 'undefined') {
                flatpickr(el, {
                    dateFormat: "Y-m-d",
                    locale: "ja"
                });
            }
        });
    }
    
    // 時間ピッカー（もし使用する場合）
    const timePickers = document.querySelectorAll('.timepicker');
    if (timePickers.length > 0) {
        timePickers.forEach(el => {
            if (typeof flatpickr !== 'undefined') {
                flatpickr(el, {
                    enableTime: true,
                    noCalendar: true,
                    dateFormat: "H:i",
                    locale: "ja"
                });
            }
        });
    }
    
    // 画像プレビュー拡大（モーダル）
    const imagePreviewLinks = document.querySelectorAll('.image-preview-link');
    imagePreviewLinks.forEach(link => {
        link.addEventListener('click', function(e) {
            e.preventDefault();
            const imageUrl = this.getAttribute('href');
            const imageTitle = this.getAttribute('data-title') || '画像プレビュー';
            
            // モーダル作成
            const modal = document.createElement('div');
            modal.classList.add('modal', 'fade');
            modal.setAttribute('tabindex', '-1');
            modal.innerHTML = `
                <div class="modal-dialog modal-lg modal-dialog-centered">
                    <div class="modal-content">
                        <div class="modal-header">
                            <h5 class="modal-title">${imageTitle}</h5>
                            <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button>
                        </div>
                        <div class="modal-body text-center">
                            <img src="${imageUrl}" class="img-fluid" alt="${imageTitle}">
                        </div>
                    </div>
                </div>
            `;
            
            document.body.appendChild(modal);
            const modalInstance = new bootstrap.Modal(modal);
            modalInstance.show();
            
            // モーダルが閉じられたら要素を削除
            modal.addEventListener('hidden.bs.modal', function() {
                document.body.removeChild(modal);
            });
        });
    });
    
    // フォームバリデーション
    const forms = document.querySelectorAll('.needs-validation');
    Array.from(forms).forEach(form => {
        form.addEventListener('submit', event => {
            if (!form.checkValidity()) {
                event.preventDefault();
                event.stopPropagation();
            }
            form.classList.add('was-validated');
        }, false);
    });
});