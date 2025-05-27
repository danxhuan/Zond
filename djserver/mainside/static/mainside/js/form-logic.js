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
            checkDownloadBtn();
        });
}

function checkDownloadBtn() {
    const downloadBtn = document.querySelector('.download-btn');
    const regions = document.querySelectorAll('#regions-list input[type="checkbox"]');
    if (downloadBtn) {
        if (regions.length > 0) {
            downloadBtn.disabled = false;
            downloadBtn.classList.remove('button--disabled');
        } else {
            downloadBtn.disabled = true;
            downloadBtn.classList.add('button--disabled');
        }
    }
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
            checkDownloadBtn();
        });
    }
    // Обработка отправки формы скачивания выбранных регионов
    const downloadForm = document.getElementById('download-form');
    const downloadSelectedBtn = document.getElementById('download-selected-btn');
    const downloadSelectedSpinner = document.getElementById('download-selected-spinner');
    if (downloadForm) {
        downloadForm.addEventListener('submit', function (e) {
            e.preventDefault();
            const checked = Array.from(document.querySelectorAll('input[name="region"]:checked')).map(cb => cb.value);
            if (checked.length === 0) {
                alert('Выберите хотя бы один регион для скачивания!');
                return;
            }
            if (downloadSelectedBtn && downloadSelectedSpinner) {
                downloadSelectedBtn.classList.add('button--disabled');
                downloadSelectedBtn.disabled = true;
                downloadSelectedSpinner.style.display = 'inline-block';
            }
            // Проверка статуса обработки перед скачиванием
            const sessionId = window.sessionId;
            if (sessionId) {
                fetch(`/api/processing-status/${sessionId}/`)
                    .then(response => response.json())
                    .then(data => {
                        if (data.status !== 'completed') {
                            alert('Обработка ещё не завершена. Скачивание будет доступно после окончания обработки.');
                            if (downloadSelectedBtn && downloadSelectedSpinner) {
                                downloadSelectedBtn.classList.remove('button--disabled');
                                downloadSelectedBtn.disabled = false;
                                downloadSelectedSpinner.style.display = 'none';
                            }
                            return;
                        }
                        // Только если обработка завершена — делаем fetch архива
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
                                window.URL.revokeObjectURL(url);
                            })
                            .finally(() => {
                                if (downloadSelectedBtn && downloadSelectedSpinner) {
                                    downloadSelectedBtn.classList.remove('button--disabled');
                                    downloadSelectedBtn.disabled = false;
                                    downloadSelectedSpinner.style.display = 'none';
                                }
                            });
                    });
            } else {
                // Если sessionId не определён, просто скачиваем (старое поведение)
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
                        window.URL.revokeObjectURL(url);
                    })
                    .finally(() => {
                        if (downloadSelectedBtn && downloadSelectedSpinner) {
                            downloadSelectedBtn.classList.remove('button--disabled');
                            downloadSelectedBtn.disabled = false;
                            downloadSelectedSpinner.style.display = 'none';
                        }
                    });
            }
        });
    }

    // Обработка скачивания результатов (основная кнопка)
    const downloadResultsBtn = document.getElementById('download-results-btn');
    const downloadResultsSpinner = document.getElementById('download-results-spinner');
    if (downloadResultsBtn && downloadResultsSpinner) {
        downloadResultsBtn.addEventListener('click', function(e) {
            e.preventDefault();
            downloadResultsBtn.classList.add('button--disabled');
            downloadResultsBtn.style.pointerEvents = 'none';
            downloadResultsSpinner.style.display = 'inline-block';

            fetch(downloadResultsBtn.href)
                .then(response => {
                    if (!response.ok) throw new Error('Ошибка скачивания');
                    return response.blob();
                })
                .then(blob => {
                    const url = window.URL.createObjectURL(blob);
                    const a = document.createElement('a');
                    a.href = url;
                    a.download = "results.zip";
                    document.body.appendChild(a);
                    a.click();
                    a.remove();
                    window.URL.revokeObjectURL(url);
                    // Скрыть кнопку после успешного скачивания
                    document.getElementById('download-section').style.display = 'none';
                })
                .catch(() => {
                    alert('Ошибка при скачивании архива');
                })
                .finally(() => {
                    downloadResultsBtn.classList.remove('button--disabled');
                    downloadResultsBtn.style.pointerEvents = '';
                    downloadResultsSpinner.style.display = 'none';
                });
        });
    }

    const kmlInput = document.getElementById('kml-upload');
    const tifInput = document.getElementById('tif-upload');
    const kmlFileList = document.getElementById('kml-file-list');
    const tifFileList = document.getElementById('tif-file-list');
    const uploadBtn = document.getElementById('upload-btn');

    function updateFileList(input, listDiv) {
        if (input && listDiv) {
            const files = Array.from(input.files);
            if (files.length > 0) {
                listDiv.innerHTML = files.map(f => `<div>${f.name}</div>`).join('');
            } else {
                listDiv.innerHTML = '';
            }
        }
    }

    function checkUploadBtn() {
        if (kmlInput && tifInput && uploadBtn) {
            if (kmlInput.files.length > 0 && tifInput.files.length > 0) {
                uploadBtn.disabled = false;
                uploadBtn.classList.remove('button--disabled');
            } else {
                uploadBtn.disabled = true;
                uploadBtn.classList.add('button--disabled');
            }
        }
    }

    if (kmlInput && kmlFileList) {
        kmlInput.addEventListener('change', function () {
            updateFileList(kmlInput, kmlFileList);
            checkUploadBtn();
        });
    }
    if (tifInput && tifFileList) {
        tifInput.addEventListener('change', function () {
            updateFileList(tifInput, tifFileList);
            checkUploadBtn();
        });
    }
    // Инициализация состояния кнопки при загрузке
    checkUploadBtn();
});

function showWarning(message) {
    const warningDiv = document.getElementById('js-warning');
    if (warningDiv) {
        warningDiv.innerHTML = `<div class="message warning"><i class="fas fa-exclamation-circle"></i> ${message}</div>`;
    }
}

function handleFormSubmit(event) {
    event.preventDefault();
    // Очищаем старые сообщения
    const messagesBlock = document.querySelector('.upload-messages');
    if (messagesBlock) messagesBlock.innerHTML = '';
    // Очищаем js-warning
    const jsWarning = document.getElementById('js-warning');
    if (jsWarning) jsWarning.innerHTML = '';
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
            if (data.tif_exists_message) {
                showWarning(data.tif_exists_message);
            }
            if (data.status === 'processing') {
                pollProcessingStatus(data.session_id);
            } else if (data.status === 'error') {
                alert(data.message);
                document.getElementById('processing-indicator').style.display = 'none';
                // Включаем кнопку при ошибке
                uploadBtn.disabled = false;
                uploadBtn.classList.remove('button--disabled');
                uploadBtn.style.background = '';
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
            uploadBtn.style.background = '';
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
                    uploadBtn.classList.remove('button--disabled');
                    uploadBtn.style.background = '';
                    // Обновляем список регионов после обработки
                    loadRegionsList();
                } else if (data.status === 'error') {
                    statusElement.textContent = `Ошибка: ${data.message}`;
                    setTimeout(() => {
                        document.getElementById('processing-indicator').style.display = 'none';
                        // Включаем кнопку при ошибке
                        uploadBtn.disabled = false;
                        uploadBtn.classList.remove('button--disabled');
                        uploadBtn.style.background = '';
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
                    uploadBtn.classList.remove('button--disabled');
                    uploadBtn.style.background = '';
                }, 3000);
            });
    };
    checkStatus();
} 