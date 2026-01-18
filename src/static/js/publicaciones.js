document.addEventListener('DOMContentLoaded', function() {
    initMap();
    showSlide(slideIndex);
});

/* --- LÓGICA DEL MAPA --- */
function initMap() {
    var latInicial = 19.4326;
    var lngInicial = -99.1332;
    var map = L.map('map').setView([latInicial, lngInicial], 13);

    L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
        maxZoom: 19,
        attribution: '&copy; OpenStreetMap'
    }).addTo(map);

    var marker = L.marker([latInicial, lngInicial], { draggable: true }).addTo(map);
    
    // Fix visualización
    setTimeout(function(){ map.invalidateSize(); }, 500);

    marker.on('dragend', function(e) {
        document.getElementById('lat').value = marker.getLatLng().lat;
        document.getElementById('lng').value = marker.getLatLng().lng;
    });
}

/* --- LÓGICA DEL CARRUSEL DE SUBIDA --- */
let slideIndex = 1;

// 1. Mostrar imagen al seleccionar archivo
function previewCarouselImage(input, index) {
    var file = input.files[0];
    if (file) {
        var reader = new FileReader();
        reader.onload = function(e) {
            // Mostrar imagen
            var img = document.getElementById('img-' + index);
            img.src = e.target.result;
            img.style.display = "block";
            
            // Ocultar placeholder
            document.getElementById('ph-' + index).style.display = "none";

            // MOSTRAR BOTÓN DE ELIMINAR
            document.getElementById('del-' + index).style.display = "flex";
        }
        reader.readAsDataURL(file);
    }
}

// 2. Función para eliminar imagen
function deleteImage(event, index) {
    // IMPORTANTE: Evita que el clic active el input file de fondo
    event.stopPropagation(); 

    // Limpiar input file
    var input = document.getElementById('file-' + index);
    input.value = ""; 

    // Ocultar imagen y quitar src
    var img = document.getElementById('img-' + index);
    img.src = "";
    img.style.display = "none";

    // Mostrar el placeholder de nuevo
    document.getElementById('ph-' + index).style.display = "block";

    // Ocultar el botón de eliminar
    document.getElementById('del-' + index).style.display = "none";
}

// Navegación (Igual que antes)
function moveSlide(n) { showSlide(slideIndex += n); }
function currentSlide(n) { showSlide(slideIndex = n); }

function showSlide(n) {
    let slides = document.getElementsByClassName("carousel-slide");
    let dots = document.getElementsByClassName("dot");
    
    if (n > slides.length) {slideIndex = 1}    
    if (n < 1) {slideIndex = slides.length}
    
    for (let i = 0; i < slides.length; i++) {
        slides[i].classList.remove("active");
        dots[i].classList.remove("active");
    }
    slides[slideIndex-1].classList.add("active");
    dots[slideIndex-1].classList.add("active");
}