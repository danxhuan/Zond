document.addEventListener("DOMContentLoaded", function () {
    const mapElement = document.querySelector("#map");

    // Инициализация карты Leaflet
    const mapInstance = L.map('map').setView([45.213657, 39.691225], 13);

    // Слой карты OpenStreetMap
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {}).addTo(mapInstance);

    // маркер на карте
    L.marker([45.213657, 39.691225]).addTo(mapInstance)
        .bindPopup('Усть-Лабинск')
        .openPopup();
});
