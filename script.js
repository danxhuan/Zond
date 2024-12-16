// Позже здесь сделаем функцию для передачи изображений

document.addEventListener("DOMContentLoaded", function () {
    const uploadButton = document.querySelector(".upload-section button");
    uploadButton.addEventListener("click", function () {
        alert("Кнопка для загрузки изображения нажата.");
    });

    const uploadSection = document.querySelector(".upload-section");

    // Пример кнопки загрузки
    uploadSection.addEventListener("dragover", function (e) {
        e.preventDefault();
        e.stopPropagation();
        uploadSection.style.backgroundColor = "#3498db";
    });

    uploadSection.addEventListener("dragleave", function (e) {
        e.preventDefault();
        e.stopPropagation();
        uploadSection.style.backgroundColor = "#2980b9";
    });

    uploadSection.addEventListener("drop", function (e) {
        e.preventDefault();
        e.stopPropagation();
        uploadSection.style.backgroundColor = "#2980b9";
        alert("Изображение загружено!");
    });
});
