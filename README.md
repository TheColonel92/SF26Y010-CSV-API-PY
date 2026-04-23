# 🗺️ CityCompare France — SAE Outils Décisionnels

Comparateur de villes françaises (>20 000 habitants) avec données en temps réel.

## 📦 Structure du projet

```
.
├── app.py                          # Application Streamlit principale
├── requirements.txt                # Dépendances Python
├── nombre-d-habitants-commune.csv  # Données INSEE (à placer ici)
└── README.md
```

## 🚀 Lancement en local

```bash
# 1. Installer les dépendances
pip install -r requirements.txt

# 2. Placer le fichier CSV dans le même dossier que app.py
#    (nombre-d-habitants-commune.csv)

# 3. Lancer l'application
streamlit run app.py
```

L'application sera accessible sur http://localhost:8501

## ☁️ Déploiement sur Streamlit Community Cloud (gratuit)

1. Créer un compte sur https://share.streamlit.io
2. Pousser le projet sur GitHub (repo public ou privé)
3. Cliquer sur "New app" > sélectionner le repo > choisir `app.py`
4. Déployer !

> ⚠️ Le fichier CSV est trop volumineux pour GitHub. Deux solutions :
> - Utiliser Git LFS : `git lfs track "*.csv"`
> - Héberger le CSV sur un bucket S3/Google Cloud et le télécharger au démarrage

## 📡 APIs utilisées (sans clé pour la plupart)

| API | Usage | Authentification |
|-----|-------|-----------------|
| **Open-Meteo** | Météo temps réel + prévisions 7j | ❌ Aucune |
| **Open-Meteo Archive** | Climatologie annuelle | ❌ Aucune |
| **Nominatim (OSM)** | Géocodage ville → lat/lon | ❌ Aucune |
| **Wikipédia REST** | Résumé + image de la ville | ❌ Aucune |
| **INSEE Données Locales** | Logement, emploi, démographie | ❌ Accès libre |
| **France Travail (Pôle Emploi)** | Offres d'emploi | 🔑 Clé optionnelle |

### Ajouter l'API France Travail (optionnel)

1. Créer un compte sur https://francetravail.io/
2. Créer une application et récupérer `client_id` + `client_secret`
3. Ajouter dans `.streamlit/secrets.toml` :
   ```toml
   [france_travail]
   client_id = "votre_client_id"
   client_secret = "votre_client_secret"
   ```
4. Décommenter la section API dans `app.py`

## 📊 Données affichées

### Onglet Général
- Photo + résumé Wikipedia de la ville
- Population (source INSEE CSV)
- Coordonnées géographiques
- Météo actuelle

### Onglet Météo & Climat
- **Prévisions 7 jours** : icône météo, temp. max/min, précipitations
- **Climatologie annuelle** : températures et précipitations mensuelles moyennes (5 dernières années)
- Statistiques annuelles : temp. moyenne, cumul pluie, mois le plus chaud

### Onglet Logement & Emploi
- Données INSEE (code commune, population)
- Estimation loyers et prix immobilier (indicatif)
- Lien vers les offres France Travail du département

### Onglet Comparaison
- **Radar chart** multi-critères (population, température, pluie, vent)
- **Tableau de synthèse** chiffrée côte-à-côte

## 🎨 Design

Interface dark editorial inspirée des dashboards cartographiques modernes :
- Typographie : Playfair Display (titres) + DM Sans (corps)
- Palette : fond #0e1117, accents bleu #4f8ef7 et orange #f7824f
- Graphiques Plotly avec thème sombre cohérent

## 👥 Groupe

Application développée dans le cadre de la SAE Outils Décisionnels.
