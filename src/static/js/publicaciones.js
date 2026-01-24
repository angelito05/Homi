/* src/static/js/publicaciones.js */

// --- INICIALIZACIÓN ÚNICA ---
document.addEventListener('DOMContentLoaded', function() {
    initMap();
    // Verificamos si existe la función antes de llamarla para evitar errores
    if (typeof showSlide === "function") {
        showSlide(slideIndex);
    }
});

/* --- LÓGICA DEL MAPA --- */
function initMap() {
    // 1. Verificar si el contenedor del mapa existe
    var mapContainer = document.getElementById('map');
    if (!mapContainer) return; 

    // 2. SOLUCIÓN AL ERROR: Verificar si ya está inicializado
    // Si Leaflet ya puso su ID en el contenedor, no lo volvemos a crear.
    if (mapContainer._leaflet_id) return; 

    var latInicial = 19.4326;
    var lngInicial = -99.1332;
    
    var map = L.map('map').setView([latInicial, lngInicial], 13);

    L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
        maxZoom: 19,
        attribution: '&copy; OpenStreetMap'
    }).addTo(map);

    var marker = L.marker([latInicial, lngInicial], { draggable: true }).addTo(map);
    
    // Referencias a inputs ocultos
    var inputLat = document.getElementById('lat');
    var inputLng = document.getElementById('lng');

    // Función para actualizar inputs
    function updateInputs(lat, lng) {
        if (inputLat) inputLat.value = lat;
        if (inputLng) inputLng.value = lng;
    }

    // Inicializar valores
    updateInputs(latInicial, lngInicial);

    // Fix visualización
    setTimeout(function(){ map.invalidateSize(); }, 500);

    // Eventos
    marker.on('dragend', function(e) {
        var pos = marker.getLatLng();
        updateInputs(pos.lat, pos.lng);
    });

    map.on('click', function(e) {
        var lat = e.latlng.lat;
        var lng = e.latlng.lng;
        marker.setLatLng([lat, lng]);
        updateInputs(lat, lng);
    });
}

/* --- LÓGICA DEL CARRUSEL DE SUBIDA --- */
let slideIndex = 1;

function previewCarouselImage(input, index) {
    var file = input.files[0];
    if (file) {
        var reader = new FileReader();
        reader.onload = function(e) {
            var img = document.getElementById('img-' + index);
            if(img) {
                img.src = e.target.result;
                img.style.display = "block";
            }
            
            var ph = document.getElementById('ph-' + index);
            if(ph) ph.style.display = "none";

            var delBtn = document.getElementById('del-' + index);
            if(delBtn) delBtn.style.display = "flex";
        }
        reader.readAsDataURL(file);
    }
}

function deleteImage(event, index) {
    event.stopPropagation(); 
    var input = document.getElementById('file-' + index);
    if(input) input.value = ""; 

    var img = document.getElementById('img-' + index);
    if(img) {
        img.src = "";
        img.style.display = "none";
    }

    var ph = document.getElementById('ph-' + index);
    if(ph) ph.style.display = "block";

    var delBtn = document.getElementById('del-' + index);
    if(delBtn) delBtn.style.display = "none";
}

function moveSlide(n) { showSlide(slideIndex += n); }
function currentSlide(n) { showSlide(slideIndex = n); }

function showSlide(n) {
    let slides = document.getElementsByClassName("carousel-slide");
    let dots = document.getElementsByClassName("dot");
    
    if (!slides || slides.length === 0) return;

    if (n > slides.length) {slideIndex = 1}    
    if (n < 1) {slideIndex = slides.length}
    
    for (let i = 0; i < slides.length; i++) {
        slides[i].classList.remove("active");
    }
    for (let i = 0; i < dots.length; i++) {
        dots[i].classList.remove("active");
    }
    
    if(slides[slideIndex-1]) slides[slideIndex-1].classList.add("active");
    if(dots[slideIndex-1]) dots[slideIndex-1].classList.add("active");
}