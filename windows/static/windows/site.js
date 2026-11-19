function escapeHtml(value) {
  return String(value).replace(/[&<>"']/g, function (char) {
    return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[char];
  });
}

function placeIcon() {
  return L.divIcon({
    className: "pin-icon",
    html: '<span class="pin-dot"></span>',
    iconSize: [22, 22],
    iconAnchor: [11, 22],
    popupAnchor: [0, -20],
  });
}

function pendingIcon() {
  return L.divIcon({
    className: "pin-icon pin-pending",
    html: '<span class="pin-dot"></span><span class="pin-badge">Pendência</span>',
    iconSize: [118, 28],
    iconAnchor: [11, 22],
    popupAnchor: [0, -20],
  });
}

function tileLayer() {
  return L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
    maxZoom: 19,
    // Django sends Referrer-Policy: same-origin. OSM refuses those tiles.
    referrerPolicy: "strict-origin-when-cross-origin",
    attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
  });
}

function initOverviewMap() {
  var element = document.getElementById("overview-map");
  var dataElement = document.getElementById("generators-data");
  if (!element || !dataElement || typeof L === "undefined") return;
  var points = JSON.parse(dataElement.textContent || "[]");
  var map = L.map(element).setView([-15.8, -47.95], 11);
  tileLayer().addTo(map);
  var bounds = [];
  points.forEach(function (point) {
    var marker = L.marker([point.lat, point.lng], {
      icon: point.pending ? pendingIcon() : placeIcon(),
    }).addTo(map);
    var stateLabel = point.pending
      ? "Há coleta a buscar."
      : "Só a localidade, sem pendência.";
    marker.bindPopup(
      "<strong>" + escapeHtml(point.name) + "</strong><br>" +
      escapeHtml(point.address) + "<br>" +
      stateLabel + "<br><a href=\"" + point.url + "\">Ver janelas</a>"
    );
    bounds.push([point.lat, point.lng]);
  });
  if (bounds.length === 1) map.setView(bounds[0], 13);
  else if (bounds.length > 1) map.fitBounds(bounds, { padding: [24, 24] });
}

function ensurePinMap() {
  var element = document.getElementById("pin-map");
  if (!element || typeof L === "undefined") return;
  if (element._pinMap) {
    setTimeout(function () { element._pinMap.invalidateSize(); }, 60);
    return;
  }
  var latInput = document.getElementById("id_latitude");
  var lngInput = document.getElementById("id_longitude");
  if (!latInput || !lngInput) return;
  var lat = parseFloat(latInput.value);
  var lng = parseFloat(lngInput.value);
  var hasPoint = !Number.isNaN(lat) && !Number.isNaN(lng);
  var map = L.map(element).setView(hasPoint ? [lat, lng] : [-15.79, -47.88], hasPoint ? 14 : 11);
  tileLayer().addTo(map);
  element._pinMap = map;
  var marker = null;

  function write(latlng) {
    latInput.value = latlng.lat.toFixed(6);
    lngInput.value = latlng.lng.toFixed(6);
  }

  function place(latlng) {
    if (!marker) {
      marker = L.marker(latlng, { draggable: true }).addTo(map);
      marker.on("dragend", function () { write(marker.getLatLng()); });
    } else {
      marker.setLatLng(latlng);
    }
    write(latlng);
  }

  if (hasPoint) place(L.latLng(lat, lng));
  map.on("click", function (event) { place(event.latlng); });
  setTimeout(function () { map.invalidateSize(); }, 60);
}

function initRoleForm() {
  var generatorFields = document.getElementById("generator-fields");
  var collectorFields = document.getElementById("collector-fields");
  if (!generatorFields || !collectorFields) return;
  var radios = document.querySelectorAll('input[name="role"]');

  function sync() {
    var selected = document.querySelector('input[name="role"]:checked');
    var role = selected ? selected.value : "";
    generatorFields.hidden = role !== "generator";
    collectorFields.hidden = role !== "collector";
    if (role === "generator") ensurePinMap();
  }

  radios.forEach(function (radio) { radio.addEventListener("change", sync); });
  sync();
}

document.addEventListener("DOMContentLoaded", function () {
  initOverviewMap();
  initRoleForm();
  var pin = document.getElementById("pin-map");
  if (pin && !pin.closest("[hidden]")) ensurePinMap();
});
