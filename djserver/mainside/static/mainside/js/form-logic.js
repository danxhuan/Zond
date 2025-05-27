// Загрузка списка регионов
function loadRegionsList() {
    fetch('/api/results-list/')
        .then(response => response.json())
        .then(data => {
            const listDiv = document.getElementById('regions-list');
            if (!listDiv) return;
            listDiv.innerHTML = '';
            data.regions.forEach(region => {
                const label = document.createElement('label');
                label.className = 'region-label';
                label.innerHTML = `<input type=\"checkbox\" name=\"region\" value=\"${region}\"> ${region}`;
                listDiv.appendChild(label);
            });
        });
}

document.addEventListener('DOMContentLoaded', function () {
    loadRegionsList();
    // Поиск по регионам
    const searchInput = document.getElementById('search-region');
    if (searchInput) {
        searchInput.addEventListener('input', function () {
            const search = this.value.toLowerCase();
            document.querySelectorAll('#regions-list label').forEach(label => {
                label.style.display = label.textContent.toLowerCase().includes(search) ? '' : 'none';
            });
        });
    }
    // Обработка отправки формы скачивания выбранных регионов
    const downloadForm = document.getElementById('download-form');
    if (downloadForm) {
        downloadForm.addEventListener('submit', function (e) {
            e.preventDefault();
            const checked = Array.from(document.querySelectorAll('input[name=\"region\"]:checked')).map(cb => cb.value);
            if (checked.length === 0) {
                alert('Выберите хотя бы один регион для скачивания!');
                return;
            }
            fetch('/api/download-selected/', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({regions: checked})
            })
                .then(response => response.blob())
                .then(blob => {
                    const url = window.URL.createObjectURL(blob);
                    const a = document.createElement('a');
                    a.href = url;
                    a.download = "selected_results.zip";
                    document.body.appendChild(a);
                    a.click();
                    a.remove();
                });
        });
    }
});

function handleFormSubmit(event) {
    event.preventDefault();
    // Очищаем старые сообщения
    const messagesBlock = document.querySelector('.upload-messages');
    if (messagesBlock) messagesBlock.innerHTML = '';
    const form = event.target;
    const formData = new FormData(form);
    const uploadBtn = document.getElementById('upload-btn');
    // Отключаем и делаем кнопку серой во время обработки
    uploadBtn.disabled = true;
    uploadBtn.classList.add('button--disabled');    // Показываем индикатор обработки
    document.getElementById('processing-indicator').style.display = 'block';
    document.getElementById('download-section').style.display = 'none';
    // Отправляем форму через AJAX
    fetch(form.action, {
        method: 'POST',
        body: formData,
        headers: {
            'X-CSRFToken': document.querySelector('[name=csrfmiddlewaretoken]').value
        }
    })
        .then(response => response.json())
        .then(data => {
            form.reset(); // Очищаем поля после отправки
            if (data.status === 'processing') {
                pollProcessingStatus(data.session_id);
            } else if (data.status === 'error') {
                alert(data.message);
                document.getElementById('processing-indicator').style.display = 'none';
                // Включаем кнопку при ошибке
                uploadBtn.disabled = false;
                uploadBtn.style.background = '#43a047';
            }
        })
        .catch(error => {
            form.reset(); // Очищаем поля даже при ошибке
            console.error('Error:', error);
            alert('Произошла ошибка при отправке формы');
            document.getElementById('processing-indicator').style.display = 'none';
            // Включаем кнопку при ошибке
            uploadBtn.disabled = false;
            uploadBtn.classList.remove('button--disabled');
        });
    return false;
}

function pollProcessingStatus(sessionId) {
    const statusElement = document.getElementById('processing-status');
    const uploadBtn = document.getElementById('upload-btn');
    const checkStatus = () => {
        fetch(`/api/processing-status/${sessionId}/`)
            .then(response => response.json())
            .then(data => {
                if (data.status === 'completed') {
                    document.getElementById('processing-indicator').style.display = 'none';
                    if (data.can_download_results) {
                        document.getElementById('download-section').style.display = 'block';
                    }
                    statusElement.textContent = 'Обработка завершена';
                    // Включаем кнопку после завершения (или можно оставить выключенной)
                    uploadBtn.disabled = false;
                    uploadBtn.style.background = '#43a047';
                    // Обновляем список регионов после обработки
                    loadRegionsList();
                } else if (data.status === 'error') {
                    statusElement.textContent = `Ошибка: ${data.message}`;
                    setTimeout(() => {
                        document.getElementById('processing-indicator').style.display = 'none';
                        // Включаем кнопку при ошибке
                        uploadBtn.disabled = false;
                        uploadBtn.style.background = '#43a047';
                    }, 3000);
                } else {
                    statusElement.textContent = data.message;
                    setTimeout(checkStatus, 2000);
                }
            })
            .catch(error => {
                console.error('Ошибка при проверке статуса:', error);
                statusElement.textContent = 'Ошибка при проверке статуса';
                setTimeout(() => {
                    document.getElementById('processing-indicator').style.display = 'none';
                    // Включаем кнопку при ошибке
                    uploadBtn.disabled = false;
                    uploadBtn.style.background = '#43a047';
                }, 3000);
            });
    };
    checkStatus();
} 