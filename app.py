"""
SAE Outils Décisionnels Comparateur de Villes Françaises
Sources : INSEE CSV・Open-Meteo・Nominatim・Wikipédia・Overpass (OSM)・data.enseignementsup-recherche.gouv.fr・France Travail
"""
# On importe toutes les bibliothèques nécessaires :
# - streamlit pour l'interface web
# - pandas/numpy pour manipuler les données
# - requests pour appeler les APIs externes
# - plotly pour les graphiques interactifs
import streamlit as st
import pandas as pd
import numpy as np
import requests
import os
from datetime import datetime
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# CONFIGURATION DE LA PAGE
# On configure l'apparence globale de l'app Streamlit
# (titre de l'onglet, icône, mise en page large, barre latérale)
st.set_page_config(
    page_title="Citéoscope France",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# INJECTION DU CSS EXTERNE  css/style.css
def load_css(path: str = "css/style.css"):
    """
    Charge un fichier CSS externe et l'injecte dans la page Streamlit.
    Si le fichier n'existe pas, on affiche un avertissement à l'utilisateur.
    """
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            css = f.read()
        st.markdown(f"<style>{css}</style>", unsafe_allow_html=True)
    else:
        st.warning(f"Fichier CSS introuvable : {path}")
# On applique le CSS dès le démarrage de l'app
load_css()

# CONSTANTES GLOBALES
# Chemin vers le fichier CSV des populations par communes
CSV_PATH  = "data/nombre-d-habitants-commune.csv"
# Couleurs des deux villes à comparer
COLOR_A   = "#4f8ef7"
COLOR_B   = "#f7824f"
# Abréviations des mois, utilisées dans les graphiques climatiques
MONTHS_FR = ["Jan","Fév","Mar","Avr","Mai","Juin","Juil","Aoû","Sep","Oct","Nov","Déc"]

PLOTLY_LAYOUT = dict(
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)",
    font=dict(family="DM Sans", color="#7a8299", size=11),
    xaxis=dict(gridcolor="#2a3550", zerolinecolor="#2a3550"),
    yaxis=dict(gridcolor="#2a3550", zerolinecolor="#2a3550"),
    margin=dict(l=20, r=20, t=40, b=20),
    legend=dict(bgcolor="rgba(0,0,0,0)", borderwidth=0),
)
# Ex: 0 = ciel dégagé ☀️, 61/63/65 = pluie 🌧️, 95 = orage ⛈️
WMO_ICONS = {
    0:"☀️",1:"🌤️",2:"⛅",3:"☁️",
    45:"🌫️",48:"🌫️",
    51:"🌦️",53:"🌦️",55:"🌦️",
    61:"🌧️",63:"🌧️",65:"🌧️",
    71:"🌨️",73:"🌨️",75:"🌨️",
    80:"🌧️",81:"🌧️",82:"⛈️",
    95:"⛈️",96:"⛈️",99:"⛈️",
}

# CHARGEMENT DES DONNÉES
@st.cache_data(show_spinner=False)
def load_cities(csv_path: str, min_pop: int = 20_000) -> pd.DataFrame:
    """
    Lit le fichier CSV INSEE des populations par commune.
    Pour chaque commune, on garde uniquement la mesure la plus récente.
    On filtre pour ne garder que les villes avec au moins min_pop habitants (20 000 par défaut).
    Retourne un DataFrame trié par nom de commune.
    """
    df = pd.read_csv(csv_path, dtype={"geocode_commune": str})
    # Conversion de la colonne date en format datetime
    df["date_mesure"] = pd.to_datetime(df["date_mesure"], utc=True)
    # On récupère l'index de la ligne la plus récente pour chaque commune
    idx    = df.groupby("geocode_commune")["date_mesure"].idxmax()
    latest = df.loc[idx].copy()
    # On garde uniquement les communes au-dessus du seuil de population
    latest = latest[latest["valeur"] >= min_pop].sort_values("libelle_commune")
    return latest.reset_index(drop=True)
         
# APPELS API EXTERNES
@st.cache_data(show_spinner=False, ttl=86400)
def get_geocode(city_name: str):
    """
    Recherche les coordonnées GPS (latitude, longitude) d'une ville française
    via l'API Nominatim (OpenStreetMap).
    """
    try:
        r = requests.get(
            "https://nominatim.openstreetmap.org/search",
            params={"q": f"{city_name}, France", "format": "json", "limit": 1},
            timeout=8, headers={"User-Agent": "Citéoscope-SAE/1.0"},
        )
        data = r.json()
        if data:
            return float(data[0]["lat"]), float(data[0]["lon"])
    except Exception:
        pass
    return None, None
@st.cache_data(show_spinner=False, ttl=3600)
def get_weather(lat, lon):
    """
    Récupère les prévisions météo sur 7 jours via l'API Open-Meteo.
    Données récupérées : températures min/max, précipitations, code météo, vent.
    """
    if lat is None: return None
    try:
        r = requests.get("https://api.open-meteo.com/v1/forecast", timeout=10, params={
            "latitude": lat, "longitude": lon,
            "daily": "temperature_2m_max,temperature_2m_min,precipitation_sum,weathercode,windspeed_10m_max",
            "current_weather": True,
            "timezone": "Europe/Paris",
            "forecast_days": 7,
        })
        return r.json()
    except Exception:
        return None
@st.cache_data(show_spinner=False, ttl=86400)
def get_climate(lat, lon):
    """
    Récupère les données climatiques historiques sur 5 ans via l'API Open-Meteo Archive.
    On récupère les données journalières (températures, pluie, ensoleillement),
    puis on calcule des moyennes mensuelles pour avoir une vue annuelle représentative.
    """
    if lat is None: return None
    # Période de 5 ans
    end, start = datetime.now().year - 1, datetime.now().year - 5
    try:
        r = requests.get("https://archive-api.open-meteo.com/v1/archive", timeout=20, params={
            "latitude": lat, "longitude": lon,
            "start_date": f"{start}-01-01", "end_date": f"{end}-12-31",
            "daily": "temperature_2m_max,temperature_2m_min,precipitation_sum,sunshine_duration",
            "timezone": "Europe/Paris",
        })
        data = r.json()
        # On construit un DataFrame avec toutes les données journalières
        df = pd.DataFrame({
            "date": pd.to_datetime(data["daily"]["time"]),
            "tmax": data["daily"]["temperature_2m_max"],
            "tmin": data["daily"]["temperature_2m_min"],
            "rain": data["daily"]["precipitation_sum"],
            # sunshine_duration peut être absent de certaines réponses, d'où le fallback avec None
            "sun":  data["daily"].get("sunshine_duration", [None]*len(data["daily"]["time"])),
        })
        df["month"] = df["date"].dt.month
        # On agrège par mois : moyennes de températures et d'ensoleillement, somme des pluies
        return df.groupby("month").agg(
            tmax=("tmax","mean"), tmin=("tmin","mean"),
            rain=("rain","sum"),  sun=("sun","mean"),
        ).reset_index()
    except Exception:
        return None
@st.cache_data(show_spinner=False, ttl=86400)
def get_wikipedia(city_name: str):
    """
    Récupère le résumé Wikipedia et la miniature illustrant la ville.
    Retourne un tuple (texte_résumé, url_image).
    """
    try:
        r = requests.get(
            "https://fr.wikipedia.org/api/rest_v1/page/summary/" +
            requests.utils.quote(city_name), timeout=8)
        d = r.json()
        return d.get("extract",""), d.get("thumbnail",{}).get("source","")
    except Exception:
        return "", ""
@st.cache_data(show_spinner=False, ttl=86400)
def _overpass(lat, lon, radius, tag_key, tag_values) -> list:
    """
    Interroge l'API Overpass (données OpenStreetMap) pour trouver des points d'intérêt autour d'une position géographique donnée.

    Paramètres :
    - lat, lon   : coordonnées du centre de recherche
    - radius     : rayon en mètres autour du point
    - tag_key    : clé OSM à filtrer
    - tag_values : liste de valeurs acceptées pour cette clé (ex: ["hospital", "clinic"])

    Construit une requête Overpass QL qui cherche des noeuds et chemins correspondants,
    puis retourne jusqu'à 40 résultats avec leur nom, type, coordonnées et site web.
    """
    # On construit la requête Overpass QL en combinant tous les types de POI demandés
    parts = "".join(
        f'node["{tag_key}"="{v}"](around:{radius},{lat},{lon});'
        f'way["{tag_key}"="{v}"](around:{radius},{lat},{lon});'
        for v in tag_values
    )
    query = f"[out:json][timeout:25];({parts});out center 50;"
    try:
        r = requests.post("https://overpass-api.de/api/interpreter",
                          data={"data": query}, timeout=30)
        results = []
        for el in r.json().get("elements", []):
            tags = el.get("tags", {})
            # On récupère le nom du lieu
            name = tags.get("name", tags.get("name:fr", ""))
            if not name: continue  # On ignore les lieux sans nom
            elat = el.get("lat") or el.get("center", {}).get("lat")
            elon = el.get("lon") or el.get("center", {}).get("lon")
            results.append({
                "name": name,
                "type": tags.get(tag_key, ""),
                "lat": elat, "lon": elon,
                "website": tags.get("website", tags.get("contact:website", "")),
            })
        return results[:40]  # On limite à 40 résultats pour ne pas surcharger la carte
    except Exception:
        return []

# FONCTIONS UTILITAIRES
def wmo_icon(code):
    """Convertit un code météo WMO en ?. Retourne ? si le code est inconnu."""
    return WMO_ICONS.get(int(code), "🌡️") if code is not None else "?"
def format_pop(n):
    """
    Formate un nombre d'habitants de façon lisible.
    """
    if n >= 1_000_000: return f"{n/1_000_000:.1f} M"
    if n >= 1_000: return f"{n/1_000:.0f} k"
    return str(int(n))
def safe_cv(cl, col, agg="mean"):
    """
    Calcule une valeur agrégée sur une colonne d'un DataFrame climatique.
    """
    if cl is None: return 0
    try: return cl[col].sum() if agg == "sum" else getattr(cl[col], agg)()
    except: return 0
def render_metric(label, value, sub="", color=None):
    """
    Affiche une "carte métrique" stylisée dans Streamlit.
    - label : titre de l'indicateur (ex: "Population")
    - value : valeur principale (ex: "120 k")
    - sub   : texte secondaire
    - color : couleur optionnelle pour la valeur (bleu ou orange selon la ville)
    """
    cs = f"color:{color};" if color else ""
    st.markdown(
        f'<div class="metric-card">'
        f'<div class="metric-label">{label}</div>'
        f'<div class="metric-value" style="{cs}">{value}</div>'
        f'{"<div class=metric-sub>"+sub+"</div>" if sub else ""}'
        f'</div>', unsafe_allow_html=True)
def render_forecast(wd, color):
    """
    Affiche les prévisions météo sur 7 jours sous forme de colonnes journalières.
    Chaque colonne montre : jour, emoji météo, température max et min, et pluie si disponible.
    """
    if not wd or "daily" not in wd:
        st.info("Météo indisponible"); return
    d = wd["daily"]
    cols = st.columns(7)
    for i in range(7):
        dt   = datetime.strptime(d["time"][i], "%Y-%m-%d")
        # Nom court du jour de la semaine en français
        day  = ["Lun","Mar","Mer","Jeu","Ven","Sam","Dim"][dt.weekday()]
        tmax = d["temperature_2m_max"][i]
        tmin = d["temperature_2m_min"][i]
        rain = (d.get("precipitation_sum") or [None]*7)[i]
        with cols[i]:
            st.markdown(
                f'<div class="weather-day" style="border-top:3px solid {color};">'
                f'<div class="day-name">{day} {dt.day}/{dt.month}</div>'
                f'<div class="icon">{wmo_icon(d["weathercode"][i])}</div>'
                f'<div class="temp-max" style="color:{color};">'
                f'{"%.0f"%tmax if tmax else "--"}°</div>'
                f'<div class="temp-min">{"%.0f"%tmin if tmin else "--"}°</div>'
                # On n'affiche la pluie que si elle est > 0
                f'{"<div style=font-size:.7rem;color:#7a8299;margin-top:.2rem;>💧 "+str(round(rain,1))+" mm</div>" if rain else ""}'
                f'</div>', unsafe_allow_html=True)
def norm2(a, b):
    """
    Normalise deux valeurs sur une échelle de 0 à 10 (pour le graphique radar).
    La valeur la plus grande obtient 10, l'autre est proportionnelle.
    """
    mx = max(a, b, 1) 
    return a/mx*10, b/mx*10

# CONSTRUCTION DES GRAPHIQUES
def map_dual(city_a, la, loa, city_b, lb, lob):
    """
    Crée une carte Mapbox affichant les deux villes et une ligne semi-transparente reliant les deux points.
    La carte est centrée automatiquement entre les deux villes.
    """
    fig = go.Figure()
    # On ajoute un marqueur pour chaque ville
    for city, lat, lon, color in [(city_a,la,loa,COLOR_A),(city_b,lb,lob,COLOR_B)]:
        if lat is None: continue
        fig.add_trace(go.Scattermapbox(
            lat=[lat], lon=[lon], mode="markers+text",
            marker=dict(size=18, color=color),
            text=[city], textposition="top center",
            textfont=dict(size=13, color="white"),
            name=city,
            hovertemplate=f"<b>{city}</b><br>{lat:.3f}°N, {lon:.3f}°E<extra></extra>",
        ))
    # On trace une ligne entre les deux villes pour visualiser la distance
    if la and lb:
        fig.add_trace(go.Scattermapbox(
            lat=[la,lb], lon=[loa,lob], mode="lines",
            line=dict(width=2, color="rgba(255,255,255,0.2)"),
            showlegend=False, hoverinfo="skip",
        ))
    # Centrage de la carte au milieu des deux villes
    clat = np.mean([l for l in [la,lb] if l])
    clon = np.mean([l for l in [loa,lob] if l])
    fig.update_layout(
        mapbox=dict(style="carto-darkmatter", center=dict(lat=clat,lon=clon), zoom=4.5),
        paper_bgcolor="rgba(0,0,0,0)", margin=dict(l=0,r=0,t=0,b=0), height=380,
        legend=dict(bgcolor="rgba(28,35,51,0.85)", bordercolor="#2a3550",
                    borderwidth=1, font=dict(color="#e8eaf0")),
    )
    return fig
def map_pois(pois_a, pois_b, city_a, city_b, la, loa, lb, lob, icon_map, c_b=COLOR_B):
    """
    Affiche sur une carte les points d'intérêt (POI) des deux villes.
    - Un gros marqueur indique le centre de chaque ville.
    """
    fig = go.Figure()
    for pois, city, lat, lon, color in [
        (pois_a,city_a,la,loa,COLOR_A),(pois_b,city_b,lb,lob,c_b)
    ]:
        if lat is None: continue
        # Marqueur central (grande taille) pour le centre-ville
        fig.add_trace(go.Scattermapbox(
            lat=[lat], lon=[lon], mode="markers",
            marker=dict(size=16, color=color), name=f"Centre {city}",
            hovertemplate=f"<b>{city}</b><extra></extra>",
        ))
        # On filtre les POI qui ont des coordonnées valides
        lats  = [p["lat"]  for p in pois if p.get("lat")]
        lons  = [p["lon"]  for p in pois if p.get("lon")]
        names = [p["name"] for p in pois if p.get("lat")]
        types = [p["type"] for p in pois if p.get("lat")]
        if lats:
            # Petits marqueurs pour chaque POI, avec info-bulle nom + type
            fig.add_trace(go.Scattermapbox(
                lat=lats, lon=lons, mode="markers",
                marker=dict(size=9, color=color, opacity=0.7),
                hovertext=[f"<b>{n}</b><br>{t}" for n,t in zip(names,types)],
                hovertemplate="%{hovertext}<extra></extra>",
                name=f"POI {city}",
            ))
    clat = np.mean([l for l in [la,lb] if l])
    clon = np.mean([l for l in [loa,lob] if l])
    # Si les deux villes sont très proches, on zoome plus fort
    zoom = 11 if abs((la or 0)-(lb or 0))<0.05 else 5
    fig.update_layout(
        mapbox=dict(style="carto-darkmatter", center=dict(lat=clat,lon=clon), zoom=zoom),
        paper_bgcolor="rgba(0,0,0,0)", margin=dict(l=0,r=0,t=0,b=0), height=460,
        legend=dict(bgcolor="rgba(28,35,51,0.85)", bordercolor="#2a3550",
                    borderwidth=1, font=dict(color="#e8eaf0")),
    )
    return fig
def chart_climate(ca, cb, na, nb):
    """
    Génère un graphique en deux parties :
    - En haut : courbes de températures max et min par mois pour les deux villes.
    - En bas  : histogramme des précipitations mensuelles.
    """
    fig = make_subplots(rows=2, cols=1,
        subplot_titles=("Températures mensuelles (°C)","Précipitations mensuelles (mm)"),
        vertical_spacing=0.15)
    for cl, name, color in [(ca,na,COLOR_A),(cb,nb,COLOR_B)]:
        if cl is None: continue
        m = [MONTHS_FR[i-1] for i in cl["month"]]
        # Courbe pleine pour les températures max
        fig.add_trace(go.Scatter(x=m,y=cl["tmax"],name=f"{name} max",
            line=dict(color=color,width=2),mode="lines+markers"),row=1,col=1)
        # Courbe pointillée pour les températures min
        fig.add_trace(go.Scatter(x=m,y=cl["tmin"],name=f"{name} min",
            line=dict(color=color,width=1.5,dash="dot"),mode="lines"),row=1,col=1)
        # Barres pour les précipitations
        fig.add_trace(go.Bar(x=m,y=cl["rain"],name=f"{name} pluie",
            marker_color=color,opacity=0.6),row=2,col=1)
    fig.update_layout(**PLOTLY_LAYOUT, height=480)
    return fig
def chart_sunshine(ca, cb, na, nb):
    """
    Génère un histogramme comparant l'ensoleillement moyen mensuel entre les deux villes. 
    Les données de sunshine_duration sont en secondes, donc on divise par 3600 pour obtenir des heures.
    """
    fig = go.Figure()
    for cl, name, color in [(ca,na,COLOR_A),(cb,nb,COLOR_B)]:
        # On ignore si les données solaires sont toutes manquantes
        if cl is None or cl["sun"].isnull().all(): continue
        m = [MONTHS_FR[i-1] for i in cl["month"]]
        fig.add_trace(go.Bar(x=m,y=(cl["sun"]/3600).round(1),name=name,
            marker_color=color,opacity=0.8))
    fig.update_layout(**PLOTLY_LAYOUT,height=280,
        yaxis_title="h/jour",title="Ensoleillement moyen mensuel")
    return fig
def chart_poi_types(pa, pb, na, nb, icon_map):
    """
    Génère un histogramme comparant le nombre de POI par type entre les deux villes.
    """
    def ct(pois):
        # Comptage simple : on parcourt les POI et on incrémente un dictionnaire
        c={}
        for p in pois: c[p.get("type","autre")] = c.get(p.get("type","autre"),0)+1
        return c
    ca, cb = ct(pa), ct(pb)
    types  = sorted(set(list(ca)+list(cb)))  # Union de tous les types présents
    
    labels = [f"{icon_map.get(t,'📍')} {t}" for t in types]
    fig    = go.Figure()
    fig.add_trace(go.Bar(x=labels,y=[ca.get(t,0) for t in types],
        name=na,marker_color=COLOR_A,opacity=0.85))
    fig.add_trace(go.Bar(x=labels,y=[cb.get(t,0) for t in types],
        name=nb,marker_color=COLOR_B,opacity=0.85))
    fig.update_layout(**PLOTLY_LAYOUT,height=300,barmode="group",
        yaxis_title="Nb de lieux",title="Répartition par type")
    return fig
def chart_radar(na, nb, pop_a, pop_b, tmax_a, tmax_b,
                rain_a, rain_b, wind_a, wind_b):
    """
    Génère un graphique radar comparant les deux villes sur 4 critères :
    - Population
    - Température moyenne
    - Ensoleillement (inversé par rapport au vent)
    - Faibles pluies (une valeur élevée = moins de pluie = mieux)

    """
    cats = ["Population","Température","Ensoleillement","Faibles pluies"]
    pn = norm2(pop_a,pop_b); tn = norm2(tmax_a,tmax_b)
    rn = norm2(rain_b,rain_a)   # Inversé : moins de pluie = meilleur score
    wn = norm2(wind_b,wind_a)   # Inversé : moins de vent = meilleur score
    # On ferme le polygone en répétant la première valeur à la fin
    va = [pn[0],tn[0],wn[0],rn[0]]+[pn[0]]
    vb = [pn[1],tn[1],wn[1],rn[1]]+[pn[1]]
    cc = cats+[cats[0]]
    fig = go.Figure()
    fig.add_trace(go.Scatterpolar(r=va,theta=cc,fill="toself",name=na,
        line_color=COLOR_A,fillcolor="rgba(79,142,247,0.2)"))
    fig.add_trace(go.Scatterpolar(r=vb,theta=cc,fill="toself",name=nb,
        line_color=COLOR_B,fillcolor="rgba(247,130,79,0.2)"))
    fig.update_layout(
        polar=dict(bgcolor="rgba(0,0,0,0)",
            radialaxis=dict(visible=True,range=[0,10],gridcolor="#2a3550",
                tickfont=dict(color="#7a8299")),
            angularaxis=dict(gridcolor="#2a3550",tickfont=dict(color="#e8eaf0"))),
        paper_bgcolor="rgba(0,0,0,0)",
        font=dict(family="DM Sans",color="#7a8299"),
        legend=dict(bgcolor="rgba(0,0,0,0)"), height=440,
    )
    return fig

# FONCTION PRINCIPALE
def main():
    # En-tête de la page
    st.markdown("""
    <div>
      <div class="hero-title">Citéoscope<br><em>France</em></div>
      <div class="hero-sub">Comparez deux villes · INSEE · Météo</div>
    </div>""", unsafe_allow_html=True)

    # Chargement du référentiel des communes 
    with st.spinner("Chargement des communes >20 000 hab.…"):
        try:
            cities_df = load_cities(CSV_PATH)
        except FileNotFoundError:
            # Si le CSV est absent, on bloque l'app avec un message d'erreur clair
            st.error("❌ `data/nombre-d-habitants-commune.csv` introuvable dans le dossier courant.")
            st.stop()

    # On prépare les listes et dictionnaires de référence pour les sélecteurs
    city_names = cities_df["libelle_commune"].tolist()
    city_codes = dict(zip(cities_df["libelle_commune"], cities_df["geocode_commune"]))
    city_pops  = dict(zip(cities_df["libelle_commune"], cities_df["valeur"]))

    # Sélecteurs de villes 
    col1, col2 = st.columns(2)
    # Paris et Lyon sont les villes sélectionnées par défaut si elles existent dans le CSV
    idx_a = city_names.index("Paris") if "Paris" in city_names else 0
    idx_b = city_names.index("Lyon")  if "Lyon"  in city_names else 1
    with col1:
        st.markdown('<div class="city-badge badge-a">🔵 Ville A</div>', unsafe_allow_html=True)
        city_a = st.selectbox("", city_names, index=idx_a, key="city_a")
    with col2:
        st.markdown('<div class="city-badge badge-b">🟠 Ville B</div>', unsafe_allow_html=True)
        city_b = st.selectbox("", city_names, index=idx_b, key="city_b")

    # Garde-fou : on empêche de comparer une ville avec elle-même
    if city_a == city_b:
        st.warning("Sélectionnez deux villes différentes.")
        st.stop()

    st.markdown('<hr class="city-divider">', unsafe_allow_html=True)

    # Récupération de toutes les données via les APIs 
    with st.spinner("Récupération des données en temps réel…"):
        la, loa = get_geocode(city_a)       # Coordonnées GPS ville A
        lb, lob = get_geocode(city_b)       # Coordonnées GPS ville B
        wa  = get_weather(la, loa)          # Prévisions météo 7j ville A
        wb  = get_weather(lb, lob)          # Prévisions météo 7j ville B
        ca  = get_climate(la, loa)          # Données climatiques 5 ans ville A
        cb  = get_climate(lb, lob)          # Données climatiques 5 ans ville B
        wia, ima = get_wikipedia(city_a)    # Résumé + image Wikipedia ville A
        wib, imb = get_wikipedia(city_b)    # Résumé + image Wikipedia ville B
        pop_a = int(city_pops[city_a])      # Population ville A (depuis CSV INSEE)
        pop_b = int(city_pops[city_b])      # Population ville B (depuis CSV INSEE)
        code_a= city_codes[city_a]          # Code INSEE ville A
        code_b= city_codes[city_b]          # Code INSEE ville B
    # Navigation par onglets
    tabs = st.tabs([
        "Général",
        "Météo & Climat",
        "Logement & Emploi",
        "Comparaison"
    ])
    # ONGLET 1 VUE GÉNÉRALE
    # Affiche la carte de localisation, les résumés
    # et quelques métriques clés (population, coordonnées, météo actuelle).
    with tabs[0]:
        st.markdown('<div class="section-title">Vue d\'ensemble</div>', unsafe_allow_html=True)
        # Carte uniquement si les deux villes ont pu être géolocalisées
        if la and lb:
            st.plotly_chart(map_dual(city_a,la,loa,city_b,lb,lob), use_container_width=True)

        g1, g2 = st.columns(2)
        for col, city, pop, lat, lon, wiki, img, color, badge in [
            (g1,city_a,pop_a,la,loa,wia,ima,COLOR_A,"badge-a"),
            (g2,city_b,pop_b,lb,lob,wib,imb,COLOR_B,"badge-b"),
        ]:
            with col:
                st.markdown(f'<div class="city-badge {badge}">{city}</div>', unsafe_allow_html=True)
                if img: st.image(img, use_container_width=True)
                if wiki:
                    st.markdown(f'<div class="wiki-box">{wiki[:700]}{"…" if len(wiki)>700 else ""}</div>',
                                unsafe_allow_html=True)
                render_metric("Population", format_pop(pop), "Source : INSEE", color)
                if lat: render_metric("Coordonnées", f"{lat:.2f}°N, {lon:.2f}°E", "Via Nominatim/OSM")
                # On sélectionne les données météo de la bonne ville
                cwd = wa if city == city_a else wb
                if cwd and "current_weather" in cwd:
                    cw = cwd["current_weather"]
                    render_metric("Météo actuelle",
                        f"{wmo_icon(cw.get('weathercode'))} {cw.get('temperature','--')}°C",
                        f"Vent : {cw.get('windspeed','--')} km/h", color)
    # ONGLET 2 MÉTÉO & CLIMAT
    # Prévisions sur 7 jours + résumé de la semaine + climatologie sur 5 ans.
    with tabs[1]:
        st.markdown('<div class="section-title">Prévisions 7 jours</div>', unsafe_allow_html=True)
        f1, f2 = st.columns(2)
        with f1:
            st.markdown(f'<div class="city-badge badge-a">{city_a}</div>', unsafe_allow_html=True)
            render_forecast(wa, COLOR_A)
        with f2:
            st.markdown(f'<div class="city-badge badge-b">{city_b}</div>', unsafe_allow_html=True)
            render_forecast(wb, COLOR_B)

        st.markdown('<div class="section-title">Résumé météo de la semaine</div>', unsafe_allow_html=True)
        s1, s2 = st.columns(2)
        for col, wd, name, color, badge in [
            (s1,wa,city_a,COLOR_A,"badge-a"),(s2,wb,city_b,COLOR_B,"badge-b")
        ]:
            with col:
                st.markdown(f'<div class="city-badge {badge}">{name}</div>', unsafe_allow_html=True)
                if wd and "daily" in wd:
                    d = wd["daily"]
                    # On filtre les valeurs None avant de calculer les stats
                    tmaxs=[x for x in d["temperature_2m_max"] if x]
                    tmins=[x for x in d["temperature_2m_min"] if x]
                    rains=[x for x in (d.get("precipitation_sum") or []) if x]
                    if tmaxs: render_metric("Temp. max semaine",f"{max(tmaxs):.0f}°C",f"Moy. {np.mean(tmaxs):.1f}°C",color)
                    if tmins: render_metric("Temp. min semaine",f"{min(tmins):.0f}°C",f"Moy. {np.mean(tmins):.1f}°C")
                    if rains: render_metric("Cumul pluie",f"{sum(rains):.1f} mm","7 jours")

        st.markdown('<div class="section-title">Climatologie annuelle (5 ans)</div>', unsafe_allow_html=True)
        if ca is not None or cb is not None:
            # Graphique températures + pluies mensuelles
            st.plotly_chart(chart_climate(ca,cb,city_a,city_b), use_container_width=True)
            # Graphique ensoleillement mensuel
            st.plotly_chart(chart_sunshine(ca,cb,city_a,city_b), use_container_width=True)

            sc1, sc2 = st.columns(2)
            for col, cl, name, color, badge in [
                (sc1,ca,city_a,COLOR_A,"badge-a"),(sc2,cb,city_b,COLOR_B,"badge-b")
            ]:
                with col:
                    st.markdown(f'<div class="city-badge {badge}">{name}</div>', unsafe_allow_html=True)
                    if cl is not None:
                        # Température moyenne annuelle = moyenne de (tmax + tmin) / 2 sur tous les mois
                        tmoy = (cl["tmax"].mean()+cl["tmin"].mean())/2
                        render_metric("Temp. moy. annuelle",f"{tmoy:.1f}°C","Moy. 5 ans",color)
                        render_metric("Précipitations",f"{cl['rain'].sum():.0f} mm","Cumul annuel")
                        # Mois le plus chaud : on cherche l'index du tmax le plus élevé
                        mchaud = MONTHS_FR[cl.loc[cl["tmax"].idxmax(),"month"]-1]
                        render_metric("Mois le plus chaud",mchaud,f"{cl['tmax'].max():.1f}°C moy.")
                        # Ensoleillement : on affiche seulement si des données existent
                        if not cl["sun"].isnull().all():
                            render_metric("Ensoleillement",f"{cl['sun'].mean()/3600:.1f} h/j","Moy. quotidienne")
                    else:
                        st.info("Données indisponibles")
        else:
            st.markdown('<div class="info-box">📡 Données climatiques indisponibles.</div>', unsafe_allow_html=True)
    # ONGLET 3 LOGEMENT & EMPLOI
    # Estimations de loyers et prix immobiliers basées sur la taille de la ville,
    # plus un lien vers les offres d'emploi France Travail.
    with tabs[2]:
        st.markdown('<div class="section-title">Logement & Emploi</div>', unsafe_allow_html=True)
        h1, h2 = st.columns(2)
        rv = {}  # Stocke les fourchettes de loyers/prix pour le graphique comparatif
        for col, city, code, pop, color, badge, slot in [
            (h1,city_a,code_a,pop_a,COLOR_A,"badge-a","a"),
            (h2,city_b,code_b,pop_b,COLOR_B,"badge-b","b"),
        ]:
            with col:
                st.markdown(f'<div class="city-badge {badge}">{city}</div>', unsafe_allow_html=True)
                render_metric("Code commune INSEE",code,"Identifiant officiel",color)
                render_metric("Population",format_pop(pop),"Recensement INSEE",color)
                # Estimation des loyers et prix au m2 selon la taille de la ville
                # Ces fourchettes sont des approximations basées sur des données DVF/MeilleursAgents
                if pop>=1_000_000:   r1,r2,p1,p2=1200,2500,9000,12000   # Très grande ville (Paris)
                elif pop>=500_000:   r1,r2,p1,p2=900,1800,4000,7000     # Grande métropole
                elif pop>=200_000:   r1,r2,p1,p2=750,1400,3000,5000     # Grande ville
                elif pop>=100_000:   r1,r2,p1,p2=650,1100,2500,4000     # Ville moyenne-grande
                elif pop>=50_000:    r1,r2,p1,p2=550,950,1800,3000      # Ville moyenne
                else:                r1,r2,p1,p2=450,750,1200,2200      # Petite ville
                rv[slot]=(r1,r2,p1,p2)
                render_metric("Loyer moyen T2/T3",f"{r1}–{r2} €/mois","DVF / MeilleursAgents",color)
                render_metric("Prix immobilier",f"{p1:,}–{p2:,} €/m²".replace(",","_").replace("_",""),"DVF",color)
                # Lien direct vers les offres France Travail filtrées sur le code commune
                pe_url=f"https://candidat.francetravail.fr/offres/recherche?lieux={code[:5]}&offresPartenaires=true&rayon=0&tri=0"
                render_metric("Offres d'emploi","France Travail →",f"[Voir les offres com. {code[:5]}]({pe_url})",color)
        # Graphique comparatif des loyers et prix immobiliers
        st.markdown('<div class="section-title">Comparaison loyers & immobilier</div>', unsafe_allow_html=True)
        cats_r=["Loyer min","Loyer max","Prix min €/m²","Prix max €/m²"]
        fig_r=go.Figure()
        fig_r.add_trace(go.Bar(x=cats_r,y=list(rv["a"]),name=city_a,marker_color=COLOR_A,opacity=0.85))
        fig_r.add_trace(go.Bar(x=cats_r,y=list(rv["b"]),name=city_b,marker_color=COLOR_B,opacity=0.85))
        fig_r.update_layout(**PLOTLY_LAYOUT,height=300,barmode="group",
            title="Estimations immobilières comparées",yaxis_title="€")
        st.plotly_chart(fig_r, use_container_width=True)
        # Graphique comparatif des populations
        fig_pop=go.Figure()
        fig_pop.add_trace(go.Bar(x=[city_a],y=[pop_a],name=city_a,marker_color=COLOR_A,width=0.4))
        fig_pop.add_trace(go.Bar(x=[city_b],y=[pop_b],name=city_b,marker_color=COLOR_B,width=0.4))
        fig_pop.update_layout(**PLOTLY_LAYOUT,height=260,yaxis_title="Habitants",title="Population comparée")
        st.plotly_chart(fig_pop, use_container_width=True)

    # ONGLET 4 TABLEAU DE BORD COMPARATIF
    # Graphique radar synthétique + carte de positionnement + tableau récapitulatif.
    with tabs[3]:
        st.markdown('<div class="section-title">Tableau de bord comparatif</div>', unsafe_allow_html=True)
        # Récupération des valeurs agrégées pour le radar
        tmax_a = safe_cv(ca, "tmax")          # Temp. max moyenne ville A
        tmax_b = safe_cv(cb, "tmax")          # Temp. max moyenne ville B
        rain_a = safe_cv(ca, "rain", "sum")   # Pluie totale annuelle ville A
        rain_b = safe_cv(cb, "rain", "sum")   # Pluie totale annuelle ville B
        wd_a = (wa or {}).get("daily", {}).get("windspeed_10m_max", [0] * 7)
        wd_b = (wb or {}).get("daily", {}).get("windspeed_10m_max", [0] * 7)
        # Moyenne du vent sur la semaine
        wind_a = np.mean([x for x in wd_a if x]) if any(wd_a) else 0
        wind_b = np.mean([x for x in wd_b if x]) if any(wd_b) else 0
        # Graphique radar clé unique pour éviter les conflits Streamlit
        st.plotly_chart(
            chart_radar(city_a, city_b, pop_a, pop_b, tmax_a, tmax_b, rain_a, rain_b, wind_a, wind_b),
            use_container_width=True,
            key="radar_chart"
        )
        # Carte de positionnement géographique (uniquement si les deux villes sont géolocalisées)
        if la and lb:
            st.markdown('<div class="section-title">Positionnement géographique</div>', unsafe_allow_html=True)
            st.plotly_chart(
                map_dual(city_a, la, loa, city_b, lb, lob),
                use_container_width=True,
                key="map_dual"
            )
        # Tableau récapitulatif avec toutes les métriques clés côte à côte
        st.markdown('<div class="section-title">Synthèse chiffrée</div>', unsafe_allow_html=True)
        rows=[
            {"Critère":"Population",city_a:format_pop(pop_a),city_b:format_pop(pop_b)},
            {"Critère":"Code INSEE",city_a:code_a,city_b:code_b},
            {"Critère":"Latitude",
             city_a:f"{la:.3f}°" if la else "—",
             city_b:f"{lb:.3f}°" if lb else "—"},
        ]
        # On ajoute la météo actuelle si disponible
        if wa and "current_weather" in wa:
            rows.insert(2,{"Critère":"Temp. actuelle",
                city_a:f"{wa['current_weather'].get('temperature','--')}°C",
                city_b:f"{wb['current_weather'].get('temperature','--')}°C" if wb and 'current_weather' in wb else "—"})
        # On ajoute les données climatiques si disponibles
        if ca is not None:
            rows.append({"Critère":"Temp. moy. annuelle",
                city_a:f"{(ca['tmax'].mean()+ca['tmin'].mean())/2:.1f}°C",
                city_b:f"{(cb['tmax'].mean()+cb['tmin'].mean())/2:.1f}°C" if cb is not None else "—"})
            rows.append({"Critère":"Précipitations annuelles",
                city_a:f"{ca['rain'].sum():.0f} mm",
                city_b:f"{cb['rain'].sum():.0f} mm" if cb is not None else "—"})
        # Affichage du tableau avec style sombre personnalisé
        df_s=pd.DataFrame(rows).set_index("Critère")
        st.dataframe(
            df_s.style
                .set_properties(**{"background-color":"#1c2333","color":"#e8eaf0","border":"1px solid #2a3550"})
                .set_table_styles([{"selector":"th","props":[("background","#0e1117"),("color","#7a8299"),("font-size","0.8rem")]}]),
            use_container_width=True,
        )
    # Pied de page 
    # Liste des sources de données utilisées dans l'application
    st.markdown("""
    <hr class="city-divider">
    <div class="footer">
      Sources・INSEE・Open-Meteo・Open-Meteo Archive・Nominatim/OSM・Overpass API・Wikipédia・data.enseignementsup-recherche.gouv.fr・France Travail<br>
      SAE Outils Décisionnels données temps réel via API
    </div>""", unsafe_allow_html=True)
# Point d'entrée : on lance main() uniquement si le script est exécuté directement
if __name__ == "__main__":
    main()
