function escapeHtml(value) {
  return String(value).replace(/[&<>"']/g, function (char) {
    return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[char];
  });
}

function readJson(id) {
  var element = document.getElementById(id);
  return element ? JSON.parse(element.textContent || "null") : null;
}

function pinIcon(pending) {
  return L.divIcon({
    className: "pin" + (pending ? " pin-pending" : ""),
    html: '<span class="pin-dot"></span>' + (pending ? '<span class="pin-badge">Coleta a buscar</span>' : ""),
    iconSize: [36, 36],
    iconAnchor: [18, 34],
    popupAnchor: [0, -32],
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
  if (!element || typeof L === "undefined") return;
  var points = readJson("generators-data") || [];
  var map = L.map(element);
  tileLayer().addTo(map);
  var bounds = [];
  points.forEach(function (point) {
    var stateLabel = point.pending
      ? "Há coleta a buscar."
      : "Só a localidade, sem pendência.";
    L.marker([point.lat, point.lng], { icon: pinIcon(point.pending), title: point.name })
      .bindPopup(
        "<strong>" + escapeHtml(point.name) + "</strong><br>" +
        escapeHtml(point.address) + "<br>" +
        stateLabel + '<br><a href="' + escapeHtml(point.url) + '">Ver janelas</a>'
      )
      .addTo(map);
    bounds.push([point.lat, point.lng]);
  });
  if (bounds.length === 0) map.setView([-15.8, -47.95], 11);
  else if (bounds.length === 1) map.setView(bounds[0], 15);
  // Extra room on the right so the "Coleta a buscar" badge is not cut off.
  else map.fitBounds(bounds, { paddingTopLeft: [40, 56], paddingBottomRight: [150, 40], maxZoom: 16 });
}

function initPlaceMap() {
  var element = document.getElementById("place-map");
  if (!element || typeof L === "undefined") return;
  var place = readJson("place-data");
  var map = L.map(element).setView(place ? [place.lat, place.lng] : [-15.8, -47.95], place ? 16 : 11);
  tileLayer().addTo(map);
  if (place) L.marker([place.lat, place.lng], { icon: pinIcon(false), title: place.name }).addTo(map);
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
      marker = L.marker(latlng, { icon: pinIcon(false), draggable: true }).addTo(map);
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
  initPlaceMap();
  initRoleForm();
  var pin = document.getElementById("pin-map");
  if (pin && !pin.closest("[hidden]")) ensurePinMap();
});
