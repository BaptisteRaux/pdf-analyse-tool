# Analyseur de Rapports SFCR

## Description
Cet outil permet d'analyser automatiquement les rapports SFCR (Solvency and Financial Condition Report) des compagnies d'assurance. Il extrait les informations clés comme le SCR, le MCR, le ratio de solvabilité et la composition des fonds propres, puis génère des visualisations et des analyses comparatives.

## Fonctionnalités
- **Extraction automatique** des données financières à partir de PDFs 
- **Analyse individuelle** de chaque rapport SFCR
- **Comparaison** entre plusieurs compagnies d'assurance
- **Visualisations** sous forme de graphiques pour chaque métrique
- **Export des données** au format Excel avec mise en forme professionnelle
- **Interface utilisateur intuitive** développée avec Streamlit

## Métriques analysées
- SCR (Capital de Solvabilité Requis)
- MCR (Minimum de Capital Requis)
- Ratio de solvabilité
- Éléments éligibles (fonds propres)
- Capital et primes
- Réserve de réconciliation
- Dettes subordonnées
- Fonds excédentaires

## Technologies utilisées
- Python
- Streamlit
- Pandas
- Matplotlib
- Altair
- API Claude (Anthropic)
- Openpyxl (pour la génération d'Excel)

## Installation

### Prérequis
- Python 3.8 ou supérieur
- Pip (gestionnaire de paquets Python)

### Étapes d'installation
1. Clonez ce dépôt :
   ```
   git clone https://github.com/BaptisteRaux/pdf-analyse-tool
   cd pdf-analyse-tool
   ```

2. Installez les dépendances si nécessaires:
   ```
   pip install -r requirements.txt
   ```

## Utilisation

1. Lancez l'application :
   ```
   python -m streamlit run app.py
   ```

2. Accédez à l'interface via votre navigateur (généralement à l'adresse http://localhost:8501)

3. Téléchargez un ou plusieurs rapports SFCR au format PDF

4. Explorez les données extraites et les visualisations générées

5. Téléchargez les résultats au format Excel pour une analyse plus approfondie
