const swiper = new Swiper('.swiper', {
    mousewheel: {
        //прокрутка колесиком на слайде с картой
        eventsTarget: '.swiper',
        noMousewheelClass: 'map-slide'
    },
    direction: 'vertical',
    speed: 1700,
    parallax: true
})

document.addEventListener('DOMContentLoaded', () => {
    document.querySelectorAll('[data-slide]').forEach(element => {
        element.addEventListener('click', (e) => {
            e.preventDefault();
            const slideIndex = parseInt(element.getAttribute('data-slide'));
            swiper.slideTo(slideIndex);
        });
    });

    // Подсветка меню при загрузке и при смене слайда
    const updateActiveMenuItem = () => {
        document.querySelectorAll('.header-menu a').forEach(link => {
            const slideIndex = parseInt(link.getAttribute('data-slide'));
            if (slideIndex === swiper.activeIndex) {
                link.classList.add('active');
            } else {
                link.classList.remove('active');
            }
        });
    };
    swiper.on('slideChange', updateActiveMenuItem);
    updateActiveMenuItem();
    document.querySelector('.slider-ui').style.pointerEvents = 'none';
    document.querySelectorAll('.header-menu a, .header-button, .button').forEach(el => {
        el.style.pointerEvents = 'auto';
    });
});

document.querySelectorAll('.header-content h1').forEach(e => {
    e.innerHTML = e.textContent.replace(/ (-|#|@){1}/g, s => s[1]+s[0]).replace(/(\S*)/g, m => {
        return m.replace(/\S(-|#|@)?/g, '<span class="letter">$&</span>')
    })
    e.querySelectorAll('.letter').forEach(function(l, i) {
        l.setAttribute('style', `z-index: -${ i }; transition-duration: ${ i/5 + 1 }s`)
    })
})

swiper.on('slideChange', function() {
    document.querySelectorAll('.header-content__slide').forEach(function(e, i) {
        return swiper.activeIndex === i ? e.classList.add('active') : e.classList.remove('active')
    })
})

document.addEventListener('DOMContentLoaded', function() {
    const map = L.map('map', {
        dragging: true,
        scrollWheelZoom: true,
        doubleClickZoom: true,
        zoomControl: true
    }).setView([45.213657, 39.691225], 13);
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        attribution: ''
    }).addTo(map);
    L.marker([45.213657, 39.691225]).addTo(map)
        .bindPopup('Усть-Лабинск')
        .openPopup();

    const mapContainer = document.getElementById('map');
    mapContainer.addEventListener('mouseover', () => {
        swiper.mousewheel.disable();
        swiper.allowTouchMove = false;
    });

    mapContainer.addEventListener('mouseout', () => {
        swiper.mousewheel.enable();
        swiper.allowTouchMove = true;
    });

    const mapContainerFullscreen = document.getElementById('map');
    const fullscreenBtn = document.getElementById('openFullscreen');

    fullscreenBtn.addEventListener('click', () => {
        mapContainerFullscreen.classList.add('fullscreen');
        
        swiper.mousewheel.disable();
        swiper.allowTouchMove = false;
        swiper.keyboard.disable();
        swiper.disable();
        
        const closeBtn = document.createElement('button');
        closeBtn.className = 'map-close-btn';
        closeBtn.innerHTML = '×';
        document.body.appendChild(closeBtn);
        
        map.invalidateSize();
        
        closeBtn.addEventListener('click', () => {
            mapContainerFullscreen.classList.remove('fullscreen');
            closeBtn.remove();
            map.invalidateSize();
            
            swiper.mousewheel.enable();
            swiper.allowTouchMove = true;
            swiper.keyboard.enable();
            swiper.enable();
        });
    });
});
