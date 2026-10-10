/* SIG intercommunal - CC de Sélestat : visualiseur open source (Leaflet + Turf).
 * Les données de la base intercommunale sont exportées en GeoJSON par
 * scripts/05_carte_web.py ; le cadastre et la recherche d'adresse viennent
 * des services de la Géoplateforme IGN (API Carto, géocodage). */
"use strict";

const DEPOT = "https://github.com/jauresmas/sig-selestat-territoires/blob/main/";
const API_CADASTRE = "https://apicarto.ign.fr/api/cadastre/parcelle";
const API_GEOCODAGE = "https://data.geopf.fr/geocodage/search";
const ZOOM_PARCELLE = 15;

const nf = (v, d = 0) => v == null || v === "" || Number.isNaN(+v) ? "—"
  : new Intl.NumberFormat("fr-FR", { maximumFractionDigits: d, minimumFractionDigits: d }).format(+v);
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) =>
  ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);
const $ = (sel) => document.querySelector(sel);

// --- Symbologie (mêmes couleurs que le projet QGIS et les planches) -------------
const ZONES = {
  U: ["Zone urbaine (U)", "#e0614f"], AUc: ["À urbaniser ouverte (AUc)", "#f29b46"],
  AUs: ["À urbaniser fermée (AUs)", "#f7c98b"], A: ["Agricole (A)", "#f3e27a"],
  N: ["Naturelle et forestière (N)", "#7cb56b"],
};
const PRESCRIPTIONS = {
  "01": ["Espace boisé classé", "#2b8a3e"], "02": ["Risques ou nuisances", "#1c7ed6"],
  "05": ["Emplacement réservé", "#e8590c"], "07": ["Patrimoine bâti ou paysager protégé", "#69b97a"],
  "18": ["Orientation d'aménagement (OAP)", "#862e9c"], autre: ["Autre prescription", "#6c757d"],
};
const SUP = {
  PM1: ["PM1 · Plans de prévention des risques", "#2c6fbb"], AC1: ["AC1 · Abords des monuments historiques", "#8e44ad"],
  AC2: ["AC2 · Sites inscrits et classés", "#d35f9a"], AC3: ["AC3 · Réserve naturelle", "#2e7d32"],
  A4: ["A4 · Berges des cours d'eau", "#5dade2"], I4: ["I4 · Lignes électriques", "#e67e22"],
  T1: ["T1 · Voies ferrées", "#555555"], autre: ["Autres servitudes", "#7f8c8d"],
};
const NATURE = {
  SIC: ["Natura 2000 · directive Habitats", "#2e8b57"], ZPS: ["Natura 2000 · directive Oiseaux", "#6b8e23"],
  ZNIEFF1: ["ZNIEFF de type I", "#c9b400"], ZNIEFF2: ["ZNIEFF de type II", "#d8c766"],
  RNR: ["Réserve naturelle régionale", "#1b5e20"], APB: ["Arrêté de protection de biotope", "#00897b"],
};
const ETATS = {
  bon: ["Bon", "#2b8a3e"], moyen: ["Moyen", "#94c47d"], surveiller: ["À surveiller", "#f2c94c"],
  deperissant: ["Dépérissant", "#e8590c"], mort: ["Mort ou dangereux", "#a61e4d"],
};
const STADES = { jeune: "jeune", adulte: "adulte", mature: "mature", senescent: "sénescent" };
const IMPLANTATIONS = { alignement: "alignement de voirie", isole: "arbre isolé", parc: "parc ou square",
  groupe: "groupe ou bosquet", equipement: "abords d'équipement" };

const couleur = (table, code) => (table[code] || table.autre || ["", "#6c757d"])[1];

// --- Carte et fonds de plan -------------------------------------------------------
const wmts = (couche, fmt = "image/png", style = "normal") =>
  `https://data.geopf.fr/wmts?SERVICE=WMTS&REQUEST=GetTile&VERSION=1.0.0&LAYER=${couche}` +
  `&STYLE=${encodeURIComponent(style)}&TILEMATRIXSET=PM&FORMAT=${fmt}` +
  "&TILEMATRIX={z}&TILEROW={y}&TILECOL={x}";
const ATTR_IGN = '© <a href="https://www.ign.fr">IGN</a>';

const carte = L.map("carte", { zoomControl: true, preferCanvas: true, minZoom: 10, maxZoom: 20 })
  .setView([48.245, 7.43], 12);
L.control.scale({ imperial: false }).addTo(carte);

const FONDS = {
  "Plan IGN": L.tileLayer(wmts("GEOGRAPHICALGRIDSYSTEMS.PLANIGNV2"), { maxZoom: 20, maxNativeZoom: 19, attribution: ATTR_IGN }),
  "Photographies": L.tileLayer(wmts("ORTHOIMAGERY.ORTHOPHOTOS", "image/jpeg"), { maxZoom: 20, maxNativeZoom: 19, attribution: ATTR_IGN }),
  "Plan gris": L.tileLayer(wmts("GEOGRAPHICALGRIDSYSTEMS.PLANIGNV2"), { maxZoom: 20, maxNativeZoom: 19, attribution: ATTR_IGN, className: "fond-gris" }),
};
document.head.insertAdjacentHTML("beforeend",
  "<style>.fond-gris{filter:grayscale(1) brightness(1.08) contrast(.85);opacity:.75}</style>");
let fondActif = FONDS["Plan gris"].addTo(carte);

const cadastre = L.tileLayer(wmts("CADASTRALPARCELS.PARCELLAIRE_EXPRESS", "image/png", "PCI vecteur"),
  { minZoom: 14, maxZoom: 20, maxNativeZoom: 19, className: "tuiles-cadastre",
    attribution: ATTR_IGN + " (Parcellaire Express)" });
// cadastre en gris discret : il sert de repère, la couleur reste au zonage et aux arbres
document.head.insertAdjacentHTML("beforeend",
  "<style>.tuiles-cadastre{filter:grayscale(1) contrast(1.3);opacity:.6}</style>");

carte.createPane("parcelle").style.zIndex = 640;
carte.createPane("arbres").style.zIndex = 630;

// --- Données ----------------------------------------------------------------------
const D = {};
const charger = (nom) => fetch(`data/${nom}.geojson`).then((r) => {
  if (!r.ok) throw new Error(`${nom} : ${r.status}`);
  return r.json();
}).then((gj) => {
  gj.features.forEach((f) => { f._bbox = turf.bbox(f); });
  D[nom] = gj;
  return gj;
});

// --- Couches thématiques ---------------------------------------------------------
const COUCHES = [
  { groupe: "Patrimoine arboré", id: "arbres", titre: "Arbres inventoriés", actif: true, legende: ETATS, rond: true },
  { groupe: "Urbanisme et servitudes", id: "zonage", titre: "Zonage des PLU", actif: true, legende: ZONES },
  { groupe: "Urbanisme et servitudes", id: "prescriptions", titre: "Prescriptions des PLU", legende: PRESCRIPTIONS },
  { groupe: "Urbanisme et servitudes", id: "informations", titre: "Informations (DPU, bruit, SIS...)" },
  { groupe: "Urbanisme et servitudes", id: "servitudes", titre: "Servitudes d'utilité publique", legende: SUP },
  { groupe: "Environnement", id: "nature", titre: "Zonages du patrimoine naturel", legende: NATURE },
  { groupe: "Référentiels", id: "cadastre", titre: "Cadastre (IGN)", actif: true, tuiles: cadastre },
  { groupe: "Référentiels", id: "communes", titre: "Limites communales", actif: true },
];

function styleCouche(id) {
  switch (id) {
    case "zonage": return (f) => ({ color: couleur(ZONES, f.properties.typezone), weight: .6,
      fillColor: couleur(ZONES, f.properties.typezone), fillOpacity: carte.getZoom() >= 16 ? .25 : .42 });
    case "prescriptions": return (f) => {
      const c = couleur(PRESCRIPTIONS, f.properties.typepsc);
      return { color: c, weight: 1, fillColor: c, fillOpacity: .22, dashArray: f.properties.typepsc === "18" ? "5 4" : null };
    };
    case "informations": return () => ({ color: "#6c757d", weight: .9, fill: false, dashArray: "2 4" });
    case "servitudes": return (f) => {
      const c = couleur(SUP, f.properties.suptype);
      return { color: c, weight: 1.1, fillColor: c, fillOpacity: .12 };
    };
    case "nature": return (f) => {
      const c = couleur(NATURE, f.properties.type_zonage);
      return { color: c, weight: 1.2, fillColor: c, fillOpacity: .22, dashArray: f.properties.type_zonage === "ZNIEFF2" ? "6 4" : null };
    };
    default: return () => ({});
  }
}

const calques = {};
let indicateurActif = null;

function couchePolygones(id, gj) {
  return L.geoJSON(gj, { style: styleCouche(id), interactive: false });
}

function coucheArbres(gj) {
  return L.geoJSON(gj, {
    pane: "arbres",
    pointToLayer: (f, ll) => L.circleMarker(ll, {
      pane: "arbres",
      radius: Math.max(3.5, Math.min(9, 3 + (f.properties.circonference_cm || 60) / 60)),
      color: f.properties.remarquable ? "#1f4e5a" : "#ffffff",
      weight: f.properties.remarquable ? 2.2 : 1,
      fillColor: couleur(ETATS, f.properties.etat_sanitaire), fillOpacity: .95,
    }),
    onEachFeature: (f, lyr) => lyr.bindPopup(() => popupArbre(f.properties)),
  });
}

function popupArbre(p) {
  const etat = ETATS[p.etat_sanitaire] || ["—", "#999"];
  return `<div class="popup"><h3>${esc(p.nom_francais)}</h3>
    <p style="margin:0 0 6px;color:#4f5a60"><i>${esc(p.essence)}</i> · ${esc(p.numero)}</p>
    <table>
      <tr><td>État sanitaire</td><td><span style="color:${etat[1]}">●</span> ${etat[0]}</td></tr>
      <tr><td>Hauteur</td><td>${nf(p.hauteur_m, 1)} m</td></tr>
      <tr><td>Circonférence</td><td>${nf(p.circonference_cm)} cm</td></tr>
      <tr><td>Stade</td><td>${esc(STADES[p.stade_dev] || "—")}</td></tr>
      <tr><td>Implantation</td><td>${esc(IMPLANTATIONS[p.implantation] || "—")}</td></tr>
      ${p.remarquable ? "<tr><td colspan=2><b>Arbre remarquable</b></td></tr>" : ""}
    </table>
    <p style="margin:6px 0 0;font-size:.72rem;color:#87929a">Position © contributeurs OpenStreetMap (ODbL), attributs simulés</p></div>`;
}

function coucheCommunes(gj) {
  return L.geoJSON(gj, {
    style: (f) => styleCommune(f),
    onEachFeature: (f, lyr) => {
      lyr.bindTooltip(f.properties.nom, { permanent: true, direction: "center", className: "etiquette-commune" });
      lyr.on("click", (e) => {
        if (carte.getZoom() >= ZOOM_PARCELLE) return;  // la fiche parcelle prend le relais
        L.DomEvent.stopPropagation(e);
        L.popup().setLatLng(e.latlng).setContent(popupCommune(f.properties)).openOn(carte);
      });
    },
  });
}
document.head.insertAdjacentHTML("beforeend", `<style>
  .etiquette-commune{background:none;border:0;box-shadow:none;font-weight:700;font-size:.8rem;color:#343a40;
    text-shadow:0 0 3px #fff,0 0 3px #fff,0 0 3px #fff}
  .etiquette-commune::before{display:none}
  .sans-etiquettes .etiquette-commune{display:none}</style>`);

function popupCommune(p) {
  const lignes = [
    ["Population", nf(p.population)], ["Document d'urbanisme", esc(p.document_urbanisme)],
    ["Adresses certifiées", `${nf(p.adresses_certifiees_pct)} %`], ["Natura 2000", `${nf(p.natura2000_pct)} %`],
    ["Zone réglementée PPRI", `${nf(p.ppri_pct)} %`], ["Arbres inventoriés", nf(p.nb_arbres)],
  ];
  return `<div class="popup"><h3>${esc(p.nom)}</h3><table>${lignes.map(([a, b]) =>
    `<tr><td>${a}</td><td>${b}</td></tr>`).join("")}</table>
    <p style="margin:6px 0 0;font-size:.74rem;color:#87929a">Zoomez pour interroger une parcelle</p></div>`;
}

function styleCommune(f) {
  const base = { color: "#343a40", weight: 1.4, dashArray: "6 4", fill: true, fillOpacity: 0 };
  if (!indicateurActif) return base;
  const v = f.properties[indicateurActif.champ];
  return { ...base, dashArray: null, color: "#ffffff", weight: 1.2, fillColor: classeCouleur(v), fillOpacity: .75 };
}

// --- Panneau des couches -------------------------------------------------------------
function legendeHTML(table, rond) {
  if (!table) return "";
  return `<div class="legende">${Object.values(table).map(([lib, c]) =>
    `<div><i class="${rond ? "rond" : ""}" style="background:${c}"></i>${esc(lib)}</div>`).join("")}</div>`;
}

function construirePanneauCouches() {
  const groupes = {};
  COUCHES.forEach((c) => { (groupes[c.groupe] ||= []).push(c); });
  $("#liste-couches").innerHTML = Object.entries(groupes).map(([g, cs]) =>
    `<div class="groupe-couches"><h3>${esc(g)}</h3>${cs.map((c) => `
      <div class="couche${c.actif ? " active" : ""}" id="bloc-${c.id}">
        <label><input type="checkbox" data-couche="${c.id}" ${c.actif ? "checked" : ""}>
          ${esc(c.titre)}<span class="nb" id="nb-${c.id}"></span></label>
        ${legendeHTML(c.legende, c.rond)}
      </div>`).join("")}</div>`).join("");
  $("#liste-couches").addEventListener("change", (e) => {
    const id = e.target.dataset.couche;
    if (id) basculer(id, e.target.checked);
  });

  $("#fonds").innerHTML = Object.keys(FONDS).map((n) =>
    `<button aria-pressed="${FONDS[n] === fondActif}" data-fond="${n}">${n}</button>`).join("");
  $("#fonds").addEventListener("click", (e) => {
    const n = e.target.dataset.fond;
    if (!n) return;
    carte.removeLayer(fondActif);
    fondActif = FONDS[n].addTo(carte);
    fondActif.bringToBack();
    document.querySelectorAll("#fonds button").forEach((b) => b.setAttribute("aria-pressed", b.dataset.fond === n));
  });
}

function basculer(id, actif) {
  const c = COUCHES.find((x) => x.id === id);
  $(`#bloc-${id}`).classList.toggle("active", actif);
  if (c.tuiles) { actif ? c.tuiles.addTo(carte) : carte.removeLayer(c.tuiles); return; }
  if (!calques[id]) return;
  actif ? calques[id].addTo(carte) : carte.removeLayer(calques[id]);
  ordonner();
}

function ordonner() {
  ["nature", "zonage", "servitudes", "prescriptions", "informations", "communes"].forEach((id) => {
    if (calques[id] && carte.hasLayer(calques[id])) calques[id].bringToFront();
  });
}

// --- Onglets -------------------------------------------------------------------------
function activerOnglet(nom) {
  document.querySelectorAll(".onglets button").forEach((b) => b.setAttribute("aria-selected", b.dataset.onglet === nom));
  document.querySelectorAll(".contenu").forEach((s) => { s.hidden = s.id !== `onglet-${nom}`; });
  if (nom !== "communes" && indicateurActif) { indicateurActif = null; calques.communes?.setStyle(styleCommune); }
  if (nom === "communes") appliquerIndicateur();
}
document.querySelector(".onglets").addEventListener("click", (e) => {
  if (e.target.dataset.onglet) activerOnglet(e.target.dataset.onglet);
});

// --- Fiche parcelle ------------------------------------------------------------------
let parcelleCalque = null;

async function ficheParcelle(latlng) {
  activerOnglet("parcelle");
  const fiche = $("#fiche");
  fiche.innerHTML = '<p class="chargement">Interrogation du cadastre…</p>';
  const geom = JSON.stringify({ type: "Point", coordinates: [+latlng.lng.toFixed(6), +latlng.lat.toFixed(6)] });
  try {
    const r = await fetch(`${API_CADASTRE}?geom=${encodeURIComponent(geom)}`);
    if (!r.ok) throw new Error(`API Carto : ${r.status}`);
    const fc = await r.json();
    if (!fc.features?.length) {
      fiche.innerHTML = '<p class="erreur">Aucune parcelle à cet endroit (domaine public non cadastré ?).</p>';
      return;
    }
    afficherFiche(fc.features[0]);
  } catch (err) {
    fiche.innerHTML = `<p class="erreur">Le service cadastral de l'IGN ne répond pas (${esc(err.message)}). Réessayez dans un instant.</p>`;
  }
}

async function rechercherParcelle(insee, section, numero) {
  activerOnglet("parcelle");
  $("#fiche").innerHTML = '<p class="chargement">Recherche de la parcelle…</p>';
  const sec = section.toUpperCase().padStart(2, "0");
  const num = numero.padStart(4, "0");
  try {
    const r = await fetch(`${API_CADASTRE}?code_insee=${insee}&section=${sec}&numero=${num}`);
    const fc = await r.json();
    if (!fc.features?.length) throw new Error("parcelle introuvable");
    afficherFiche(fc.features[0], true);
  } catch (err) {
    $("#fiche").innerHTML = `<p class="erreur">Parcelle ${esc(insee)} ${esc(sec)} ${esc(num)} : ${esc(err.message)}.</p>`;
  }
}

function intersecte(parcelle, interieur, couche) {
  const bb = turf.bbox(parcelle);
  return (D[couche]?.features || []).filter((f) => {
    const b = f._bbox;
    if (b[0] > bb[2] || b[2] < bb[0] || b[1] > bb[3] || b[3] < bb[1]) return false;
    try { return turf.booleanIntersects(interieur, f); } catch { return false; }
  });
}

function afficherFiche(parcelle, centrer = false) {
  const p = parcelle.properties;
  if (parcelleCalque) carte.removeLayer(parcelleCalque);
  parcelleCalque = L.geoJSON(parcelle, { pane: "parcelle", interactive: false,
    style: { color: "#1f4e5a", weight: 3, fillColor: "#1f4e5a", fillOpacity: .12 } }).addTo(carte);
  if (centrer) carte.fitBounds(parcelleCalque.getBounds(), { maxZoom: 18, padding: [40, 40] });

  const commune = D.communes?.features.find((f) => f.properties.code_insee === p.code_insee);
  if (!commune) {
    $("#fiche").innerHTML = `<p class="erreur">La parcelle ${esc(p.idu)} est hors du territoire intercommunal.</p>`;
    return;
  }
  let interieur = parcelle;
  try {
    const b = turf.buffer(parcelle, -0.5, { units: "meters" });
    if (b && turf.area(b) > 1) interieur = b;
  } catch { /* parcelle trop petite : on garde la géométrie d'origine */ }
  const surf = turf.area(parcelle);

  const zones = intersecte(parcelle, interieur, "zonage").map((z) => {
    let part = null;
    try { const i = turf.intersect(parcelle, z); part = i ? 100 * turf.area(i) / surf : null; } catch { /* géométrie complexe */ }
    return { ...z.properties, part };
  }).sort((a, b) => (b.part || 0) - (a.part || 0));
  const presc = dedoublonner(intersecte(parcelle, interieur, "prescriptions").map((f) => f.properties), (x) => x.type_libelle + x.libelle);
  const infos = dedoublonner(intersecte(parcelle, interieur, "informations").map((f) => f.properties), (x) => x.type_libelle + x.libelle);
  const sup = dedoublonner(intersecte(parcelle, interieur, "servitudes").map((f) => f.properties), (x) => x.suptype + x.objet);
  const nature = dedoublonner(intersecte(parcelle, interieur, "nature").map((f) => f.properties), (x) => x.type_zonage + x.nom);
  const arbres = (D.arbres?.features || []).filter((a) => turf.booleanPointInPolygon(a, parcelle));
  const c = commune.properties;

  const liste = (items, rendu, vide) => items.length
    ? `<ul>${items.map(rendu).join("")}</ul>` : `<p class="aucun">${vide}</p>`;
  const doc = c.document_urbanisme === "Non publié"
    ? "Aucun document d'urbanisme publié sur le Géoportail de l'Urbanisme : se renseigner en mairie."
    : `${esc(c.document_urbanisme)} approuvé le ${new Date(c.date_approbation).toLocaleDateString("fr-FR")}` +
      (c.derniere_procedure ? ` (dernière procédure : ${esc(c.derniere_procedure)})` : "");

  $("#fiche").innerHTML = `<div class="fiche">
    <div class="fiche-entete">
      <h3>Parcelle ${esc(p.section)} ${esc(p.numero)} · ${esc(c.nom)}</h3>
      <p>Identifiant ${esc(p.idu)} · fiche éditée le ${new Date().toLocaleDateString("fr-FR")}</p>
    </div>
    <h2>Identification</h2>
    <dl>
      <dt>Commune</dt><dd>${esc(c.nom)} (${esc(p.code_insee)})</dd>
      <dt>Section · numéro</dt><dd>${esc(p.section)} · ${esc(p.numero)}</dd>
      <dt>Contenance cadastrale</dt><dd>${nf(p.contenance)} m²</dd>
      <dt>Surface calculée</dt><dd>${nf(surf)} m²</dd>
    </dl>
    <h2>Document d'urbanisme</h2>
    <p class="note" style="margin:0 0 8px">${doc}</p>
    ${liste(zones, (z) => `<li class="zone" style="--c:${couleur(ZONES, z.typezone)}">
        <b>Zone ${esc(z.libelle)}${z.part != null ? ` · ${nf(z.part)} % de la parcelle` : ""}</b>
        <small>${esc(z.libelong || (ZONES[z.typezone] || [""])[0])}</small>
        ${z.url_reglement && z.url_reglement !== "None" ? `<br><a href="${esc(z.url_reglement)}" target="_blank" rel="noopener">Règlement écrit (PDF)</a>` : ""}</li>`,
      "Pas de zonage du PLU sur cette parcelle.")}
    <h2>Prescriptions</h2>
    ${liste(presc, (x) => `<li><b>${esc(x.type_libelle)}</b><small>${esc(x.libelle)}</small></li>`, "Aucune prescription.")}
    <h2>Informations</h2>
    ${liste(infos, (x) => `<li><b>${esc(x.type_libelle)}</b><small>${esc(x.libelle)}</small></li>`, "Aucune information reportée.")}
    <h2>Servitudes d'utilité publique</h2>
    ${liste(sup, (x) => `<li style="border-left-color:${couleur(SUP, x.suptype)}"><b>${esc(x.suptype)} · ${esc(x.categorie_libelle)}</b><small>${esc(x.objet)}</small></li>`,
      "Aucune servitude recensée au Géoportail de l'Urbanisme.")}
    <h2>Patrimoine naturel</h2>
    ${liste(nature, (x) => `<li style="border-left-color:${couleur(NATURE, x.type_zonage)}"><b>${esc(x.libelle_type)}</b><small>${esc(x.nom)}</small>
        ${x.url_inpn ? `<br><a href="${esc(x.url_inpn)}" target="_blank" rel="noopener">Fiche INPN</a>` : ""}</li>`,
      "Hors zonage du patrimoine naturel.")}
    <h2>Patrimoine arboré</h2>
    ${liste(arbres, (a) => `<li style="border-left-color:${couleur(ETATS, a.properties.etat_sanitaire)}"><b>${esc(a.properties.nom_francais)} · ${esc(a.properties.numero)}</b>
        <small>État : ${esc((ETATS[a.properties.etat_sanitaire] || ["—"])[0])} · ${nf(a.properties.hauteur_m, 1)} m</small></li>`,
      "Aucun arbre inventorié sur la parcelle.")}
    <p class="avertissement">Document d'information sans valeur juridique, établi à partir des données
      publiées (Géoportail de l'Urbanisme, IGN, INPN). Seul un certificat d'urbanisme délivré par la
      commune fait foi. Projet de démonstration, étude indépendante.</p>
    <div class="actions">
      <button class="bouton" onclick="window.print()">Imprimer la fiche</button>
      <button class="bouton secondaire" id="centrer">Centrer la carte</button>
    </div></div>`;
  $("#centrer").onclick = () => carte.fitBounds(parcelleCalque.getBounds(), { maxZoom: 18, padding: [40, 40] });
}

function dedoublonner(items, cle) {
  const vus = new Set();
  return items.filter((x) => { const k = cle(x); if (vus.has(k)) return false; vus.add(k); return true; });
}

carte.on("click", (e) => {
  if (carte.getZoom() >= ZOOM_PARCELLE) ficheParcelle(e.latlng);
});
const infoZoom = L.control({ position: "bottomleft" });
infoZoom.onAdd = () => { const d = L.DomUtil.create("div", "info-echelle"); d.id = "info-zoom"; return d; };
infoZoom.addTo(carte);
function majInfoZoom() {
  $("#info-zoom").textContent = carte.getZoom() >= ZOOM_PARCELLE
    ? "Cliquez sur une parcelle pour sa fiche de renseignements"
    : "Zoomez pour interroger le cadastre";
  document.body.classList.toggle("sans-etiquettes", carte.getZoom() >= 15);
}
carte.on("zoomend", () => {
  majInfoZoom();
  calques.zonage?.setStyle(styleCouche("zonage"));
});
majInfoZoom();

// --- Recherche : adresse (géocodage IGN) ou référence cadastrale ------------------------
let communesInsee = [];
let suggestions = [];
const champ = $("#q");
const listeSugg = $("#suggestions");
let minuterie = null;

champ.addEventListener("input", () => {
  clearTimeout(minuterie);
  const q = champ.value.trim();
  if (q.length < 3 || /^\d{5}\s/.test(q)) { listeSugg.hidden = true; return; }
  minuterie = setTimeout(() => geocoder(q), 250);
});

async function geocoder(q) {
  try {
    const r = await fetch(`${API_GEOCODAGE}?q=${encodeURIComponent(q)}&index=address&limit=10&lat=48.245&lon=7.43`);
    const gj = await r.json();
    suggestions = (gj.features || []).filter((f) => communesInsee.includes(f.properties.citycode)).slice(0, 6);
    listeSugg.innerHTML = suggestions.length
      ? suggestions.map((f, i) => `<li role="option" data-i="${i}">${esc(f.properties.name)}<small>${esc(f.properties.postcode)} ${esc(f.properties.city)}</small></li>`).join("")
      : '<li aria-disabled="true">Aucune adresse dans les 12 communes</li>';
    listeSugg.hidden = false;
  } catch { listeSugg.hidden = true; }
}

listeSugg.addEventListener("click", (e) => {
  const li = e.target.closest("li[data-i]");
  if (li) choisirAdresse(suggestions[+li.dataset.i]);
});

function choisirAdresse(f) {
  listeSugg.hidden = true;
  champ.value = f.properties.label;
  const [lon, lat] = f.geometry.coordinates;
  carte.setView([lat, lon], 18);
  ficheParcelle(L.latLng(lat, lon));
}

$("#recherche").addEventListener("submit", (e) => {
  e.preventDefault();
  const q = champ.value.trim();
  const ref = q.match(/^(\d{5})\s+([0-9A-Za-z]{1,2})\s+(\d{1,4})$/);
  if (ref) { listeSugg.hidden = true; rechercherParcelle(ref[1], ref[2], ref[3]); return; }
  if (suggestions[0]) choisirAdresse(suggestions[0]);
});
document.addEventListener("click", (e) => { if (!e.target.closest(".recherche")) listeSugg.hidden = true; });
document.addEventListener("click", (e) => {
  const ex = e.target.dataset?.exemple;
  if (ex) { const [i, s, n] = ex.split(" "); champ.value = ex; rechercherParcelle(i, s, n); }
});

// --- Onglet communes ---------------------------------------------------------------------
const INDICATEURS = [
  { champ: "adresses_certifiees_pct", titre: "Adresses certifiées par la commune", unite: "%", dec: 0 },
  { champ: "logements_sans_adresse", titre: "Logements sans adresse à moins de 30 m", unite: "", dec: 0 },
  { champ: "densite_hab_km2", titre: "Densité de population", unite: "hab./km²", dec: 0 },
  { champ: "zone_au_ha", titre: "Zones à urbaniser du PLU", unite: "ha", dec: 0 },
  { champ: "ppri_pct", titre: "Part réglementée par un PPRI", unite: "%", dec: 0 },
  { champ: "natura2000_pct", titre: "Part en Natura 2000", unite: "%", dec: 0 },
  { champ: "znieff_pct", titre: "Part en ZNIEFF", unite: "%", dec: 0 },
  { champ: "nb_arbres", titre: "Arbres inventoriés", unite: "", dec: 0 },
];
const PALETTE = ["#e6f2f0", "#b4d9d3", "#7dbdb4", "#479c93", "#1f6f6a"];
let bornes = [];

function classeCouleur(v) {
  if (v == null || v === "") return "#f1f3f5";
  for (let i = bornes.length - 1; i >= 0; i--) if (+v >= bornes[i]) return PALETTE[i];
  return PALETTE[0];
}

function appliquerIndicateur() {
  if (!D.communes) return;
  indicateurActif = INDICATEURS.find((i) => i.champ === $("#indicateur").value) || INDICATEURS[0];
  const vals = D.communes.features.map((f) => +f.properties[indicateurActif.champ] || 0);
  const min = Math.min(...vals), max = Math.max(...vals);
  bornes = PALETTE.map((_, i) => min + (max - min) * i / PALETTE.length);
  calques.communes.setStyle(styleCommune);
  if (!carte.hasLayer(calques.communes)) calques.communes.addTo(carte);
  $("#legende-indicateur").innerHTML = PALETTE.map((c, i) =>
    `<span style="--c:${c}">${nf(bornes[i], indicateurActif.dec)}</span>`).join("");
  const lignes = [...D.communes.features].sort((a, b) =>
    (+b.properties[indicateurActif.champ] || 0) - (+a.properties[indicateurActif.champ] || 0));
  $("#table-communes").innerHTML = `<table class="communes"><thead><tr><th>Commune</th><th>Population</th>
    <th>${esc(indicateurActif.titre)}${indicateurActif.unite ? ` (${indicateurActif.unite})` : ""}</th></tr></thead><tbody>
    ${lignes.map((f) => `<tr data-insee="${f.properties.code_insee}"><td>${esc(f.properties.nom)}</td>
      <td>${nf(f.properties.population)}</td><td>${nf(f.properties[indicateurActif.champ], indicateurActif.dec)}</td></tr>`).join("")}
    </tbody></table>
    <p class="note">Source : vue <code>ref_admin.mv_indicateurs_commune</code> de la base PostGIS,
      également exportée en <a href="${DEPOT}livrables/04_Echanges/open_data/indicateurs_communes.csv">CSV</a>.</p>`;
}

function construireOngletCommunes() {
  $("#indicateur").innerHTML = INDICATEURS.map((i) => `<option value="${i.champ}">${esc(i.titre)}</option>`).join("");
  $("#indicateur").addEventListener("change", appliquerIndicateur);
  $("#table-communes").addEventListener("click", (e) => {
    const tr = e.target.closest("tr[data-insee]");
    if (!tr) return;
    const f = D.communes.features.find((x) => x.properties.code_insee === tr.dataset.insee);
    carte.fitBounds(L.geoJSON(f).getBounds(), { padding: [20, 20] });
  });
}

// --- Onglet données (catalogue) -----------------------------------------------------------
async function construireCatalogue() {
  const cat = await fetch("data/catalogue.json").then((r) => r.json());
  const niveaux = ["toutes", "ouverte", "interne", "restreinte"];
  let filtre = "toutes";
  const rendre = () => {
    $("#catalogue").innerHTML = cat.filter((f) => filtre === "toutes" || f.niveau_diffusion === filtre).map((f) => `
      <article class="jeu"><h3>${esc(f.titre)}<span class="badge ${f.niveau_diffusion}">${esc(f.niveau_diffusion)}</span></h3>
        <p>${esc(f.resume)}</p>
        ${f.motif_restriction ? `<p><i>${esc(f.motif_restriction)}</i></p>` : ""}
        <div class="meta"><span>${esc(f.producteur)}</span><span>${esc(f.licence)}</span>
          <span>${esc(f.millesime)}</span><span>${nf(f.nb_objets)} objets</span>
          <span><code>${esc(f.table_nom)}</code></span></div>
        <div class="meta" style="margin-top:4px">
          <a href="${DEPOT}livrables/05_Metadonnees/iso19139/${f.table_nom.replace(".", "__")}.xml" target="_blank" rel="noopener">Fiche ISO 19139</a>
          ${f.source_url ? `<a href="${esc(f.source_url)}" target="_blank" rel="noopener">Source</a>` : ""}</div>
      </article>`).join("");
  };
  $("#filtres-diffusion").innerHTML = niveaux.map((n) =>
    `<button class="fonds-btn" aria-pressed="${n === filtre}" data-niveau="${n}">${n === "toutes" ? "Tous les jeux" : n}</button>`).join("");
  $("#filtres-diffusion").classList.add("fonds");
  $("#filtres-diffusion").addEventListener("click", (e) => {
    if (!e.target.dataset.niveau) return;
    filtre = e.target.dataset.niveau;
    document.querySelectorAll("#filtres-diffusion button").forEach((b) => b.setAttribute("aria-pressed", b.dataset.niveau === filtre));
    rendre();
  });
  rendre();
}

// --- Démarrage ----------------------------------------------------------------------------
(async function demarrer() {
  construirePanneauCouches();
  construireOngletCommunes();
  cadastre.addTo(carte);
  const noms = ["epci", "communes", "zonage", "arbres", "prescriptions", "informations", "servitudes", "nature"];
  await Promise.all(noms.map((n) => charger(n).catch((err) => console.error(err))));
  communesInsee = D.communes.features.map((f) => f.properties.code_insee);

  L.geoJSON(D.epci, { interactive: false, style: { color: "#1f4e5a", weight: 3, fill: false } }).addTo(carte);
  calques.communes = coucheCommunes(D.communes);
  calques.arbres = coucheArbres(D.arbres);
  ["zonage", "prescriptions", "informations", "servitudes", "nature"].forEach((id) => {
    calques[id] = couchePolygones(id, D[id]);
  });
  COUCHES.forEach((c) => {
    if (c.actif && calques[c.id]) calques[c.id].addTo(carte);
    const n = D[c.id]?.features.length;
    if (n) $(`#nb-${c.id}`).textContent = nf(n);
  });
  ordonner();
  carte.fitBounds(L.geoJSON(D.epci).getBounds(), { padding: [10, 10] });
  construireCatalogue();
})();
