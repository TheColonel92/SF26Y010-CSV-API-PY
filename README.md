# CityCompare France SAE Outils Décisionnels

Comparateur de villes françaises (>20 000 habitants) avec données en temps réel.

## Structure du projet

```
.
├── app.py                          # Application Streamlit principale
├── requirements.txt                # Dépendances Python
├── nombre-d-habitants-commune.csv  # Données INSEE (à placer ici)
└── README.md
```

## Lancement en local

```bash
# 1. Installer les dépendances
pip install -r requirements.txt

# 2. Placer le fichier CSV dans le même dossier que app.py
#    (nombre-d-habitants-commune.csv)

# 3. Lancer l'application
streamlit run app.py
```

L'application sera accessible sur http://localhost:8501

## APIs utilisées

| API | Usage |
|
| **Open-Meteo** | Météo temps réel + prévisions 7j 
| **Open-Meteo Archive** | Climatologie annuelle 
| **Nominatim (OSM)** | Géocodage ville → lat/lon 
| **Wikipédia REST** | Résumé + image de la ville 
| **INSEE Données Locales** | Logement, emploi, démographie 
| **France Travail (Pôle Emploi)** | Offres d'emploi

## Affichage des données 

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

