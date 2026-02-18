#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import pandas as pd
import re
import numpy as np
import streamlit as st
import matplotlib.pyplot as plt
import requests
from io import BytesIO
import altair as alt
import openpyxl

API_KEY = ""

PROMPT_TEMPLATE_BASE = """
Analyse le document et donne les réponses sous cette forme EXACTE, sans aucun texte supplémentaire :
1) SCR : X€
2) MCR : X€
3) Ratio de solvabilité : X%

IMPORTANT : 
- Si tu trouves une valeur en millions d'euros (M€), convertis-la en euros (multiplie par 1 000 000)
- Si tu trouves une valeur en milliards d'euros (Md€), convertis-la en euros (multiplie par 1 000 000 000)
- Donne uniquement les chiffres, sans aucune explication
- Respecte EXACTEMENT le format demandé
"""

PROMPT_TEMPLATE_FONDS_PROPRES = """
Analyse le document et donne les réponses sous cette forme EXACTE, sans aucun texte supplémentaire :
1) Éléments éligibles (total des fonds propres) : X€
2) Capital et primes : X€
3) Réserve de réconciliation : X€
4) Dettes subordonnées : X€
5) Fonds excédentaires : X€

IMPORTANT : 
- Si tu trouves une valeur en millions d'euros (M€), convertis-la en euros (multiplie par 1 000 000)
- Si tu trouves une valeur en milliards d'euros (Md€), convertis-la en euros (multiplie par 1 000 000 000)
- Pour le capital et primes, si tu trouves ces éléments séparément (capital social + primes d'émission), additionne-les et donne uniquement le total
- Donne uniquement les chiffres, sans aucune explication ni détail
- Respecte EXACTEMENT le format demandé
- N'ajoute pas de tirets, de puces ou d'autres caractères
- N'ajoute pas de texte explicatif
"""

PROMPT_TEMPLATE_SCR_DETAIL = """
Analyse le document et donne les réponses sous cette forme EXACTE, sans aucun texte supplémentaire :
1) SCR Risque de Marché : X€
2) SCR Risque de Contrepartie : X€
3) SCR Risque de Souscription Vie : X€
4) SCR Risque de Souscription Santé : X€
5) SCR Risque de Souscription Non-Vie : X€
6) SCR Risque Opérationnel : X€
7) Effet de Diversification : X€

IMPORTANT : 
- Si tu trouves une valeur en millions d'euros (M€), convertis-la en euros (multiplie par 1 000 000)
- Si tu trouves une valeur en milliards d'euros (Md€), convertis-la en euros (multiplie par 1 000 000 000)
- Donne uniquement les chiffres, sans aucune explication
- Respecte EXACTEMENT le format demandé
- Si une valeur n'est pas disponible, indique "Non disponible"
- Pour l'Effet de Diversification, indique la valeur avec un signe négatif si c'est une réduction du SCR
"""

PROMPT_TEMPLATE_ACTIFS = """
Analyse le document et donne les réponses sous cette forme EXACTE, sans aucun texte supplémentaire :
1) Total des actifs : X€
2) Obligations : X€
3) Actions : X€
4) Fonds d'investissement : X€
5) Produits dérivés : X€
6) Immobilier : X€
7) Trésorerie et dépôts : X€
8) Participations : X€
9) Autres actifs : X€

IMPORTANT : 
- Si tu trouves une valeur en millions d'euros (M€), convertis-la en euros (multiplie par 1 000 000)
- Si tu trouves une valeur en milliards d'euros (Md€), convertis-la en euros (multiplie par 1 000 000 000)
- Donne uniquement les chiffres, sans aucune explication
- Respecte EXACTEMENT le format demandé
- Si une valeur n'est pas disponible, indique "Non disponible"
- Les informations peuvent etre présentées sous différentes normes ou catégories (comme Solvabilité 1, Solvabilité 2, IFRS, etc.), choisit toujours la colonne "Solvabilité 2 ou Solvabilité II"
- Pour le total des actifs, cherche le "Total de l'actif" ou "Total actif"
- Les obligations peuvent aussi être appelées "Titres obligataires" ou "Titres à revenu fixe"
- Les actions peuvent aussi être appelées "Titres de participation" ou "Titres à revenu variable"
- Les fonds d'investissement peuvent aussi être appelés "OPCVM" ou "Fonds communs de placement"
- IMPORTANT : Les informations peuvent se trouver à plusieurs endroits différents dans le document, comme "Actifs",  "Investissements", "Placements" ou "Portefeuille d'investissement".
"""

QUESTION_TEMPLATE_BASE = """
Réponds UNIQUEMENT avec les informations demandées, sans aucun texte supplémentaire :
0) Nom de la société : 
1) SCR : 
2) MCR : 
3) Ratio de solvabilité : 
"""

QUESTION_TEMPLATE_FONDS_PROPRES = """
Réponds UNIQUEMENT avec les informations demandées, sans aucun texte supplémentaire :
1) Éléments éligibles (total des fonds propres) : 
2) Capital et primes : 
3) Réserve de réconciliation : 
4) Dettes subordonnées : 
5) Fonds excédentaires : 

Pour le capital et primes, si tu trouves ces éléments séparément (capital social + primes d'émission), additionne-les et donne uniquement le total.
"""

QUESTION_TEMPLATE_SCR_DETAIL = """
Réponds UNIQUEMENT avec les informations demandées, sans aucun texte supplémentaire :
1) SCR Risque de Marché : 
2) SCR Risque de Contrepartie : 
3) SCR Risque de Souscription Vie : 
4) SCR Risque de Souscription Santé : 
5) SCR Risque de Souscription Non-Vie : 
6) SCR Risque Opérationnel : 
7) Effet de Diversification : 
"""

QUESTION_TEMPLATE_ACTIFS = """
Réponds UNIQUEMENT avec les informations demandées, sans aucun texte supplémentaire :
1) Total des actifs : 
2) Obligations : 
3) Actions : 
4) Fonds d'investissement : 
5) Produits dérivés : 
6) Immobilier : 
7) Trésorerie et dépôts : 
8) Participations : 
9) Autres actifs : 
"""

def convert_value(value_str, unit_pattern):
    """
    Convertit une valeur textuelle en valeur numérique en tenant compte de l'unité.
    
    Args:
        value_str (str): La chaîne de caractères contenant la valeur numérique
        unit_pattern (str): La chaîne complète contenant l'unité (€, M€, Md€)
    
    Returns:
        float: La valeur convertie en euros, ou np.nan si la conversion échoue
    """
    if "Non disponible" in value_str:
        return np.nan
        
    value_str = value_str.replace(" ", "").replace(",", ".")
    try:
        value = float(value_str)
        if "Md€" in unit_pattern or "milliard" in unit_pattern:
            return value * 1_000_000_000
        elif "M€" in unit_pattern or "million" in unit_pattern:
            return value * 1_000_000
        else:
            return value
    except ValueError:
        return np.nan

def parse_base_text(text):
    """
    Extrait les informations de base (nom de société, SCR, MCR, ratio de solvabilité) 
    à partir du texte fourni par l'API ChatPDF.
    
    Args:
        text (str): Le texte brut contenant les informations à extraire
    
    Returns:
        DataFrame: Un DataFrame contenant les informations extraites
    """
    patterns = {
        'company': r"0\)\s*Nom de la société\s*:\s*(.+)",
        'scr': r"1\)\s*SCR\s*:\s*([\d\s]+)€",
        'mcr': r"2\)\s*MCR\s*:\s*([\d\s]+)€",
        'ratio': r"3\)\s*Ratio de solvabilité\s*:\s*([\d,\.]+)\s*%"
    }
    
    data = []
    current_entry = {
        'Société': None,
        'SCR (€)': np.nan,
        'MCR (€)': np.nan,
        'Ratio de solvabilité (%)': np.nan
    }
    
    for line in text.splitlines():
        for key, pattern in patterns.items():
            match = re.search(pattern, line)
            if match:
                if key == 'company':
                    if current_entry['Société'] is not None:
                        data.append(current_entry.copy())
                    current_entry = {
                        'Société': match.group(1).strip(), 
                        'SCR (€)': np.nan, 
                        'MCR (€)': np.nan, 
                        'Ratio de solvabilité (%)': np.nan
                    }
                elif key == 'scr':
                    current_entry['SCR (€)'] = int(match.group(1).replace(" ", ""))
                elif key == 'mcr':
                    current_entry['MCR (€)'] = int(match.group(1).replace(" ", ""))
                elif key == 'ratio':
                    current_entry['Ratio de solvabilité (%)'] = float(match.group(1).replace(",", "."))
    
    if current_entry['Société'] is not None:
        data.append(current_entry)
    return pd.DataFrame(data)

def parse_fonds_propres_text(text):
    """
    Extrait les informations sur les fonds propres à partir du texte fourni par l'API ChatPDF.
    Gère différents formats de présentation des valeurs (€, M€, Md€).
    
    Args:
        text (str): Le texte brut contenant les informations à extraire
    
    Returns:
        DataFrame: Un DataFrame contenant les informations sur les fonds propres
    """
    patterns = {
        'elements_eligibles': r"1\)\s*Éléments éligibles[^:]*:\s*([\d\s,\.]+)(?:€|Md€|M€)",
        'capital_primes': r"2\)\s*Capital et primes\s*:\s*([\d\s,\.]+)(?:€|Md€|M€)",
        'reserve_reconciliation': r"3\)\s*Réserve de réconciliation\s*:\s*([\d\s,\.]+)(?:€|Md€|M€)",
        'dettes_subordonnees': r"4\)\s*Dettes subordonnées\s*:\s*([\d\s,\.]+)(?:€|Md€|M€)",
        'fonds_excedentaires': r"5\)\s*Fonds excédentaires\s*:\s*([\d\s,\.]+)(?:€|Md€|M€)"
    }
    
    # Patterns alternatifs pour capturer les valeurs en milliards ou millions
    alt_patterns = {
        'elements_eligibles': r"Éléments éligibles[^:]*:\s*([\d\s,\.]+)\s*(?:Md€|milliards|milliard)",
        'capital_primes': r"Capital et primes\s*:\s*([\d\s,\.]+)\s*(?:Md€|milliards|milliard)",
        'reserve_reconciliation': r"Réserve de réconciliation\s*:\s*([\d\s,\.]+)\s*(?:Md€|milliards|milliard)",
        'dettes_subordonnees': r"Dettes subordonnées\s*:\s*([\d\s,\.]+)\s*(?:Md€|milliards|milliard)",
        'fonds_excedentaires': r"Fonds excédentaires\s*:\s*([\d\s,\.]+)\s*(?:Md€|milliards|milliard)"
    }
    
    # Patterns pour millions
    million_patterns = {
        'elements_eligibles': r"Éléments éligibles[^:]*:\s*([\d\s,\.]+)\s*(?:M€|millions|million)",
        'capital_primes': r"Capital et primes\s*:\s*([\d\s,\.]+)\s*(?:M€|millions|million)",
        'reserve_reconciliation': r"Réserve de réconciliation\s*:\s*([\d\s,\.]+)\s*(?:M€|millions|million)",
        'dettes_subordonnees': r"Dettes subordonnées\s*:\s*([\d\s,\.]+)\s*(?:M€|millions|million)",
        'fonds_excedentaires': r"Fonds excédentaires\s*:\s*([\d\s,\.]+)\s*(?:M€|millions|million)"
    }
    
    data = []
    current_entry = {
        'Éléments éligibles (€)': np.nan,
        'Capital et primes (€)': np.nan,
        'Réserve de réconciliation (€)': np.nan,
        'Dettes subordonnées (€)': np.nan,
        'Fonds excédentaires (€)': np.nan
    }
    
    for key, pattern in patterns.items():
        match = re.search(pattern, text)
        if match:
            value_str = match.group(1)
            unit_pattern = match.group(0)
            value = convert_value(value_str, unit_pattern)
            
            if key == 'elements_eligibles':
                current_entry['Éléments éligibles (€)'] = value
            elif key == 'capital_primes':
                current_entry['Capital et primes (€)'] = value
            elif key == 'reserve_reconciliation':
                current_entry['Réserve de réconciliation (€)'] = value
            elif key == 'dettes_subordonnees':
                current_entry['Dettes subordonnées (€)'] = value
            elif key == 'fonds_excedentaires':
                current_entry['Fonds excédentaires (€)'] = value
    
    for key, pattern in alt_patterns.items():
        column_mapping = {
            'elements_eligibles': 'Éléments éligibles (€)',
            'capital_primes': 'Capital et primes (€)',
            'reserve_reconciliation': 'Réserve de réconciliation (€)',
            'dettes_subordonnees': 'Dettes subordonnées (€)',
            'fonds_excedentaires': 'Fonds excédentaires (€)'
        }
        
        column_name = column_mapping[key]
        
        if pd.isna(current_entry[column_name]):
            match = re.search(pattern, text)
            if match:
                value_str = match.group(1)
                unit_pattern = match.group(0)
                value = convert_value(value_str, unit_pattern)
                current_entry[column_name] = value
    
    for key, pattern in million_patterns.items():
        column_name = column_mapping[key]
        
        if pd.isna(current_entry[column_name]):
            match = re.search(pattern, text)
            if match:
                value_str = match.group(1)
                unit_pattern = match.group(0)
                value = convert_value(value_str, unit_pattern)
                current_entry[column_name] = value
    
    if pd.isna(current_entry['Éléments éligibles (€)']):
        match = re.search(r"Éléments éligibles.*?(\d[\d\s,\.]+)(?:€|Md€|M€)", text, re.IGNORECASE)
        if match:
            value_str = match.group(1)
            unit_pattern = match.group(0)
            current_entry['Éléments éligibles (€)'] = convert_value(value_str, unit_pattern)
    
    data.append(current_entry)
    return pd.DataFrame(data)

def parse_scr_detail_text(text):
    """
    Extrait les détails des composantes du SCR à partir du texte fourni par l'API ChatPDF.
    
    Args:
        text (str): Le texte brut contenant les informations à extraire
    
    Returns:
        DataFrame: Un DataFrame contenant les composantes détaillées du SCR
    """
    patterns = {
        'scr_marche': r"1\)\s*SCR Risque de Marché\s*:\s*([\d\s,\.]+)(?:€|Md€|M€|Non disponible)",
        'scr_contrepartie': r"2\)\s*SCR Risque de Contrepartie\s*:\s*([\d\s,\.]+)(?:€|Md€|M€|Non disponible)",
        'scr_vie': r"3\)\s*SCR Risque de Souscription Vie\s*:\s*([\d\s,\.]+)(?:€|Md€|M€|Non disponible)",
        'scr_sante': r"4\)\s*SCR Risque de Souscription Santé\s*:\s*([\d\s,\.]+)(?:€|Md€|M€|Non disponible)",
        'scr_non_vie': r"5\)\s*SCR Risque de Souscription Non-Vie\s*:\s*([\d\s,\.]+)(?:€|Md€|M€|Non disponible)",
        'scr_operationnel': r"6\)\s*SCR Risque Opérationnel\s*:\s*([\d\s,\.]+)(?:€|Md€|M€|Non disponible)",
        'effet_diversification': r"7\)\s*Effet de Diversification\s*:\s*([\-]?[\d\s,\.]+)(?:€|Md€|M€|Non disponible)"
    }
    
    data = []
    current_entry = {
        'SCR Risque de Marché (€)': np.nan,
        'SCR Risque de Contrepartie (€)': np.nan,
        'SCR Risque de Souscription Vie (€)': np.nan,
        'SCR Risque de Souscription Santé (€)': np.nan,
        'SCR Risque de Souscription Non-Vie (€)': np.nan,
        'SCR Risque Opérationnel (€)': np.nan,
        'Effet de Diversification (€)': np.nan
    }
    
    for key, pattern in patterns.items():
        match = re.search(pattern, text)
        if match:
            value_str = match.group(1)
            unit_pattern = match.group(0)
            value = convert_value(value_str, unit_pattern)
            
            column_mapping = {
                'scr_marche': 'SCR Risque de Marché (€)',
                'scr_contrepartie': 'SCR Risque de Contrepartie (€)',
                'scr_vie': 'SCR Risque de Souscription Vie (€)',
                'scr_sante': 'SCR Risque de Souscription Santé (€)',
                'scr_non_vie': 'SCR Risque de Souscription Non-Vie (€)',
                'scr_operationnel': 'SCR Risque Opérationnel (€)',
                'effet_diversification': 'Effet de Diversification (€)'
            }
            
            current_entry[column_mapping[key]] = value
    
    data.append(current_entry)
    return pd.DataFrame(data)

def parse_actifs_text(text):
    """
    Extrait les informations sur la composition des actifs à partir du texte fourni par l'API ChatPDF.
    Calcule automatiquement le total des actifs si celui-ci n'est pas disponible mais que les composantes le sont.
    
    Args:
        text (str): Le texte brut contenant les informations à extraire
    
    Returns:
        DataFrame: Un DataFrame contenant les informations sur les actifs
    """
    patterns = {
        'total_actifs': r"1\)\s*Total des actifs\s*:\s*([\d\s,\.]+)(?:€|Md€|M€|Non disponible)",
        'obligations': r"2\)\s*Obligations\s*:\s*([\d\s,\.]+)(?:€|Md€|M€|Non disponible)",
        'actions': r"3\)\s*Actions\s*:\s*([\d\s,\.]+)(?:€|Md€|M€|Non disponible)",
        'fonds': r"4\)\s*Fonds d'investissement\s*:\s*([\d\s,\.]+)(?:€|Md€|M€|Non disponible)",
        'derives': r"5\)\s*Produits dérivés\s*:\s*([\d\s,\.]+)(?:€|Md€|M€|Non disponible)",
        'immobilier': r"6\)\s*Immobilier\s*:\s*([\d\s,\.]+)(?:€|Md€|M€|Non disponible)",
        'tresorerie': r"7\)\s*Trésorerie et dépôts\s*:\s*([\d\s,\.]+)(?:€|Md€|M€|Non disponible)",
        'participations': r"8\)\s*Participations\s*:\s*([\d\s,\.]+)(?:€|Md€|M€|Non disponible)",
        'autres': r"9\)\s*Autres actifs\s*:\s*([\d\s,\.]+)(?:€|Md€|M€|Non disponible)"
    }
    
    data = []
    current_entry = {
        'Total des actifs (€)': np.nan,
        'Obligations (€)': np.nan,
        'Actions (€)': np.nan,
        'Fonds d\'investissement (€)': np.nan,
        'Produits dérivés (€)': np.nan,
        'Immobilier (€)': np.nan,
        'Trésorerie et dépôts (€)': np.nan,
        'Participations (€)': np.nan,
        'Autres actifs (€)': np.nan
    }
    
    for key, pattern in patterns.items():
        match = re.search(pattern, text)
        if match:
            value_str = match.group(1)
            unit_pattern = match.group(0)
            value = convert_value(value_str, unit_pattern)
            
            column_mapping = {
                'total_actifs': 'Total des actifs (€)',
                'obligations': 'Obligations (€)',
                'actions': 'Actions (€)',
                'fonds': 'Fonds d\'investissement (€)',
                'derives': 'Produits dérivés (€)',
                'immobilier': 'Immobilier (€)',
                'tresorerie': 'Trésorerie et dépôts (€)',
                'participations': 'Participations (€)',
                'autres': 'Autres actifs (€)'
            }
            
            current_entry[column_mapping[key]] = value

    if pd.isna(current_entry['Total des actifs (€)']):
        components = [
            current_entry['Obligations (€)'],
            current_entry['Actions (€)'],
            current_entry['Fonds d\'investissement (€)'],
            current_entry['Produits dérivés (€)'],
            current_entry['Immobilier (€)'],
            current_entry['Trésorerie et dépôts (€)'],
            current_entry['Participations (€)'],
            current_entry['Autres actifs (€)']
        ]
        
        valid_components = [c for c in components if not pd.isna(c)]
        
        if valid_components:  
            current_entry['Total des actifs (€)'] = sum(valid_components)
    
    data.append(current_entry)
    return pd.DataFrame(data)

def add_pdf_from_file(uploaded_file):
    """
    Télécharge un fichier PDF vers l'API ChatPDF et obtient un identifiant unique.
    
    Cette fonction prend un fichier PDF téléchargé via Streamlit, l'envoie à l'API ChatPDF
    et retourne l'identifiant source qui sera utilisé pour interroger le document.
    
    Args:
        uploaded_file: L'objet fichier PDF obtenu via st.file_uploader
    
    Returns:
        str: L'identifiant source (source_id) du PDF dans l'API ChatPDF, ou None en cas d'erreur
    """
    url = "https://api.chatpdf.com/v1/sources/add-file"
    headers = {"x-api-key": API_KEY}
    
    try:
        files = {"file": (uploaded_file.name, uploaded_file, "application/pdf")}
        response = requests.post(url, headers=headers, files=files)
        response.raise_for_status() 
        return response.json()["sourceId"]
    except Exception as e:
        st.error(f"Erreur lors du téléchargement du PDF: {str(e)}")
        return None

def chat_with_pdf(source_id, question, prompt=None):
    """
    Envoie une question à l'API ChatPDF et retourne la réponse.
    
    Args:
        source_id (str): L'identifiant source du PDF
        question (str): La question à poser
        prompt (str, optional): Un prompt spécifique à utiliser
    
    Returns:
        str: La réponse de l'API ChatPDF, ou None en cas d'erreur
    """
    url = "https://api.chatpdf.com/v1/chats/message"
    headers = {"x-api-key": API_KEY, "Content-Type": "application/json"}
    
    messages = []
    if prompt:
        messages.append({"role": "assistant", "content": prompt})
    messages.append({"role": "user", "content": question})
    
    data = {"sourceId": source_id, "messages": messages}
    
    try:
        response = requests.post(url, json=data, headers=headers)
        response.raise_for_status()
        content = response.json()["content"]
        
        return content
    except requests.exceptions.RequestException as e:
        st.error(f"Erreur lors de la requête à ChatPDF : {e}")
        if e.response is not None:
            st.error(f"Réponse du serveur : {e.response.text}")
        return None

def compute_additional_statistics(df):
    stats = {}
    for col in ["SCR (€)", "MCR (€)", "Ratio de solvabilité (%)"]:
        stats[col] = {
            "Moyenne": df[col].mean(),
            "Médiane": df[col].median(),
            "Écart-type": df[col].std(),
            "Minimum": df[col].min(),
            "Maximum": df[col].max()
        }
    return pd.DataFrame(stats).T

def display_altair_chart(df, metric, chart_type, color):
    base = alt.Chart(df).encode(
        x=alt.X('Société:N', title='Société', sort=None),
        y=alt.Y(f'{metric}:Q', title=metric),
        tooltip=['Société', f'{metric}:Q']
    )
    if chart_type == "Barres":
        chart = base.mark_bar(color=color)
    elif chart_type == "Lignes":
        chart = base.mark_line(color=color, point=True)
    elif chart_type == "Scatter":
        chart = base.mark_point(color=color, size=100)
    else:
        chart = base.mark_bar(color=color)

    chart = chart.properties(width=600, height=400).interactive()
    st.altair_chart(chart, use_container_width=True)

def display_data(df_solvency, show_full_analysis=False):
    """
    Affiche les données extraites d'un PDF sous forme de tableaux et de graphiques.
    
    Args:
        df_solvency (DataFrame): Le DataFrame contenant les données à afficher
        show_full_analysis (bool): Si True, affiche l'analyse complète avec tous les graphiques
    """
    st.subheader("Aperçu des données")
    st.dataframe(df_solvency)

    if show_full_analysis:
        st.subheader("Métriques clés")
        col1, col2, col3 = st.columns(3)
        col1.metric("Nombre de sociétés", len(df_solvency))
        col2.metric("SCR moyen (€)", f"{df_solvency['SCR (€)'].mean():,.2f} €")
        col3.metric("Ratio de solvabilité moyen (%)", f"{df_solvency['Ratio de solvabilité (%)'].mean():.2f} %")

        st.subheader("Statistiques supplémentaires")
        stats_df = compute_additional_statistics(df_solvency)
        st.dataframe(stats_df)

        st.subheader("Graphique statique")
        option = st.selectbox("Choisissez une visualisation statique", ("SCR (€)", "MCR (€)", "Ratio de solvabilité (%)"))
        try:
            plt.style.use('seaborn')
        except OSError:
            plt.style.use('ggplot')

        fig, ax = plt.subplots(figsize=(12, 8))
        if option == "SCR (€)":
            ax.bar(df_solvency["Société"], df_solvency["SCR (€)"].fillna(0), color='skyblue')
            ax.set_title("SCR par société", fontsize=16, fontweight='bold')
            ax.set_ylabel("Montant (€)", fontsize=14)
        elif option == "MCR (€)":
            ax.bar(df_solvency["Société"], df_solvency["MCR (€)"].fillna(0), color='salmon')
            ax.set_title("MCR par société", fontsize=16, fontweight='bold')
            ax.set_ylabel("Montant (€)", fontsize=14)
        else:
            ax.bar(df_solvency["Société"], df_solvency["Ratio de solvabilité (%)"].fillna(0), color='lightgreen')
            ax.set_title("Ratio de solvabilité par société", fontsize=16, fontweight='bold')
            ax.set_ylabel("Ratio (%)", fontsize=14)

        ax.tick_params(axis='x', labelsize=12, rotation=45)
        ax.tick_params(axis='y', labelsize=12)
        ax.grid(True)
        fig.tight_layout()
        st.pyplot(fig)
        st.subheader("Graphique interactif Altair")
        chart_type = st.sidebar.radio("Type de graphique interactif", ("Barres", "Lignes", "Scatter"))
        color = st.sidebar.color_picker("Choisissez la couleur", "#1f77b4")
        metric = st.selectbox("Sélectionnez la métrique", ("SCR (€)", "MCR (€)", "Ratio de solvabilité (%)"))
        display_altair_chart(df_solvency, metric, chart_type, color)

def download_excel(df, filename="analyse_sfcr.xlsx"):
    """
    Crée un fichier Excel contenant les données extraites et le rend téléchargeable.
    Organise les données en plusieurs onglets thématiques et ajuste automatiquement la largeur des colonnes.
    Exclut la ligne "Moyenne" du fichier Excel.
    
    Args:
        df (DataFrame): Le DataFrame contenant les données à exporter
        filename (str): Le nom du fichier Excel à générer
    """
    output = BytesIO()
    writer = pd.ExcelWriter(output, engine='openpyxl')
    
    df_societes = df[df['Société'] != 'Moyenne'].copy()
    df_transposed = df_societes.set_index('Société').transpose()
    df_transposed.index.name = 'Métrique'
    df_transposed.to_excel(writer, sheet_name='Données')
    
    # Ajouter une feuille "Fonds propres"
    fonds_propres_columns = [
        'Société', 
        'Éléments éligibles (€)', 
        'Capital et primes (€)', 
        'Réserve de réconciliation (€)', 
        'Dettes subordonnées (€)', 
        'Fonds excédentaires (€)'
    ]
    df_fonds_propres = df_societes[fonds_propres_columns].set_index('Société').transpose()
    df_fonds_propres.index.name = 'Métrique'
    df_fonds_propres.to_excel(writer, sheet_name='Fonds propres')
    
    # Ajouter une feuille "SCR"
    scr_columns = [
        'Société', 
        'SCR (€)', 
        'MCR (€)', 
        'Ratio de solvabilité (%)',
        'SCR Risque de Marché (€)',
        'SCR Risque de Contrepartie (€)',
        'SCR Risque de Souscription Vie (€)',
        'SCR Risque de Souscription Santé (€)',
        'SCR Risque de Souscription Non-Vie (€)',
        'SCR Risque Opérationnel (€)',
        'Effet de Diversification (€)'
    ]
    df_scr = df_societes[scr_columns].set_index('Société').transpose()
    df_scr.index.name = 'Métrique'
    df_scr.to_excel(writer, sheet_name='SCR')
    
    # Ajouter une feuille "Actifs"
    actifs_columns = [
        'Société', 
        'Total des actifs (€)',
        'Obligations (€)',
        'Actions (€)', 
        'Fonds d\'investissement (€)', 
        'Produits dérivés (€)', 
        'Immobilier (€)', 
        'Trésorerie et dépôts (€)', 
        'Participations (€)', 
        'Autres actifs (€)'
    ]
    df_actifs = df_societes[actifs_columns].set_index('Société').transpose()
    df_actifs.index.name = 'Métrique'
    df_actifs.to_excel(writer, sheet_name='Actifs')
    
    for sheet_name in writer.sheets:
        worksheet = writer.sheets[sheet_name]
        for idx, col in enumerate(worksheet.columns, 1):
            max_length = 0
            column = col[0].column_letter  
            
            for cell in col:
                try:
                    if len(str(cell.value)) > max_length:
                        max_length = len(str(cell.value))
                except:
                    pass
            
            adjusted_width = (max_length + 2) * 1.2
            worksheet.column_dimensions[column].width = adjusted_width
    
    writer.close()
    output.seek(0)
    st.download_button(
        label="📥 Télécharger les données (Excel)",
        data=output.getvalue(),
        file_name=filename,
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

def create_matplotlib_figure(data, title, x_label, y_label, color='steelblue', moyenne=None):
    """
    Crée un graphique à barres avec matplotlib pour visualiser une métrique spécifique.
    
    Args:
        data (DataFrame): Le DataFrame contenant les données
        title (str): Le titre du graphique
        x_label (str): Le nom de la colonne à utiliser pour l'axe X
        y_label (str): Le nom de la colonne à utiliser pour l'axe Y
        color (str): La couleur des barres
        moyenne (float, optional): La valeur moyenne à afficher comme ligne horizontale
    
    Returns:
        Figure: Un objet Figure matplotlib
    """
    fig, ax = plt.subplots(figsize=(12, 8), dpi=120)
    bars = ax.bar(data["Société"], data[y_label], color=color)
    if moyenne is not None:
        ax.axhline(y=moyenne, color='red', linestyle='--', alpha=0.8)
        ax.annotate(f'Moyenne: {moyenne:,.2f}', 
                    xy=(1, moyenne),
                    xytext=(5, 5),
                    textcoords='offset points',
                    ha='left',
                    va='bottom',
                    color='red',
                    fontweight='bold')

    ax.set_title(title, fontsize=18, fontweight='bold')
    ax.set_xlabel(x_label, fontsize=14)
    ax.set_ylabel(y_label, fontsize=14)
    ax.tick_params(axis='x', labelsize=12, rotation=45)
    ax.tick_params(axis='y', labelsize=12)
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.grid(True, linestyle='--', alpha=0.6)
    for bar in bars:
        height = bar.get_height()
        ax.annotate(f'{height:,.2f}',
                    xy=(bar.get_x() + bar.get_width()/2, height),
                    xytext=(0, 3),
                    textcoords="offset points",
                    ha='center', va='bottom', fontsize=10)
    
    fig.tight_layout()
    return fig

def create_scr_pie_chart(df, societe):
    """
    Crée un graphique en camembert pour visualiser la répartition des composantes du SCR d'une société.
    
    Args:
        df (DataFrame): Le DataFrame contenant les données
        societe (str): Le nom de la société à analyser
    
    Returns:
        Figure: Un objet Figure matplotlib, ou None si les données sont insuffisantes
    """
    if societe not in df['Société'].values:
        return None
    
    data = df[df['Société'] == societe].iloc[0]
    
    scr_components = {
        'Risque de Marché': data['SCR Risque de Marché (€)'],
        'Risque de Contrepartie': data['SCR Risque de Contrepartie (€)'],
        'Risque de Souscription Vie': data['SCR Risque de Souscription Vie (€)'],
        'Risque de Souscription Santé': data['SCR Risque de Souscription Santé (€)'],
        'Risque de Souscription Non-Vie': data['SCR Risque de Souscription Non-Vie (€)'],
        'Risque Opérationnel': data['SCR Risque Opérationnel (€)'],
        'Effet de Diversification': data['Effet de Diversification (€)']
    }
    
    scr_components = {k: v for k, v in scr_components.items() if not pd.isna(v) and (k != 'Effet de Diversification' and v > 0)}
    
    if not scr_components:
        return None
    
    fig, ax = plt.subplots(figsize=(10, 8), dpi=100)
    wedges, texts, autotexts = ax.pie(
        scr_components.values(), 
        labels=scr_components.keys(),
        autopct='%1.1f%%',
        startangle=90,
        shadow=False,
        explode=[0.05] * len(scr_components),
        textprops={'fontsize': 12}
    )
    
    ax.axis('equal')
    ax.set_title(f'Répartition du SCR pour {societe}', fontsize=16, fontweight='bold')
    ax.legend(wedges, scr_components.keys(), title="Composantes du SCR", 
              loc="center left", bbox_to_anchor=(1, 0, 0.5, 1))
    
    plt.tight_layout()
    return fig

def create_scr_waterfall_chart(df, societe):
    """
    Crée un graphique en cascade pour visualiser la composition du SCR d'une société,
    montrant comment les différentes composantes contribuent au SCR total.
    
    Args:
        df (DataFrame): Le DataFrame contenant les données
        societe (str): Le nom de la société à analyser
    
    Returns:
        Figure: Un objet Figure matplotlib, ou None si les données sont insuffisantes
    """
    if societe not in df['Société'].values:
        return None
    
    data = df[df['Société'] == societe].iloc[0]
    
    components = [
        ('Risque de Marché', data['SCR Risque de Marché (€)']),
        ('Risque de Contrepartie', data['SCR Risque de Contrepartie (€)']),
        ('Risque de Souscription Vie', data['SCR Risque de Souscription Vie (€)']),
        ('Risque de Souscription Santé', data['SCR Risque de Souscription Santé (€)']),
        ('Risque de Souscription Non-Vie', data['SCR Risque de Souscription Non-Vie (€)']),
        ('Risque Opérationnel', data['SCR Risque Opérationnel (€)']),
        ('Effet de Diversification', data['Effet de Diversification (€)']),
        ('SCR Total', data['SCR (€)'])
    ]
    
    components = [(name, value) for name, value in components if not pd.isna(value)]
    
    if len(components) < 3:
        return None
    
    fig, ax = plt.subplots(figsize=(12, 8), dpi=100)
    
    names = [comp[0] for comp in components]
    values = [comp[1] for comp in components]
    colors = ['#1f77b4'] * (len(components) - 1)
    colors.append('#2ca02c')
    bars = ax.bar(names, values, color=colors)
    
    for bar in bars:
        height = bar.get_height()
        if height < 0:
            va = 'top'
            y_pos = height - 0.05 * max(values)
        else:
            va = 'bottom'
            y_pos = height + 0.05 * max(values)
        
        ax.text(
            bar.get_x() + bar.get_width()/2,
            y_pos,
            f'{height:,.0f} €',
            ha='center',
            va=va,
            fontweight='bold'
        )
    
    ax.set_title(f'Composition du SCR pour {societe}', fontsize=16, fontweight='bold')
    ax.set_ylabel('Montant (€)', fontsize=14)
    ax.tick_params(axis='x', labelsize=12, rotation=45)
    ax.tick_params(axis='y', labelsize=12)
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.grid(True, linestyle='--', alpha=0.6, axis='y')
    
    plt.tight_layout()
    return fig

def get_predefined_prompts():
    """
    Retourne un dictionnaire de prompts prédéfinis pour les questions courantes.
    
    Returns:
        dict: Un dictionnaire de prompts prédéfinis
    """
    return {
        "Analyse du SCR": "Analyse en détail la composition du SCR. Donne la répartition des différents modules de risques (marché, souscription, etc.) et leurs montants, attention à bien convertir les montants qui peuvent être en millions d'euros. Explique quels sont les risques principaux.",
        "Analyse des fonds propres": "Analyse la composition des fonds propres. Détaille les différents tiers (Tier 1, 2, 3) et leur montant (attention à bien convertir si en millions d'euros). Compare avec l'année précédente si disponible et explique l'évolution.",
        "Analyse du ratio de solvabilité": "Explique le ratio de solvabilité actuel et son évolution. Compare avec l'année précédente et explique les facteurs qui ont influencé ce ratio. Précise si des mesures particulières ont été prises pour maintenir ou améliorer ce ratio.",
        "Analyse du MCR": "Donne les détails sur le MCR (Minimum Capital Requirement). Précise son montant (attention à bien convertir si en millions d'euros), explique son calcul et son évolution par rapport à l'année précédente.",
        "Analyse des actifs": "Analyse les actifs détenus par l'entreprise. Détaille les différents types d'actifs et leur montant (attention à bien convertir si en millions d'euros). Compare avec l'année précédente si disponible et explique l'évolution."
    }

def process_pdf_unified(source_id, pdf_name):
    """
    Traite un PDF en extrayant toutes les informations nécessaires via l'API ChatPDF.
    Combine les informations de base, les fonds propres, les détails du SCR et les actifs.
    
    Args:
        source_id (str): L'identifiant source du PDF
        pdf_name (str): Le nom du fichier PDF
    
    Returns:
        DataFrame: Un DataFrame pandas contenant toutes les informations extraites
    """
    base_response = chat_with_pdf(source_id, QUESTION_TEMPLATE_BASE, prompt=PROMPT_TEMPLATE_BASE)
    df_base = parse_base_text(base_response)
    
    if df_base.empty or 'Société' not in df_base.columns:
        df_base = pd.DataFrame({
            'Société': [f"Société inconnue ({pdf_name})"],
            'SCR (€)': [np.nan],
            'MCR (€)': [np.nan],
            'Ratio de solvabilité (%)': [np.nan]
        })
    
    societe = df_base['Société'].iloc[0] if not df_base.empty else f"Société inconnue ({pdf_name})"
    
    # Extraction du détail des fonds propres
    fonds_propres_response = chat_with_pdf(source_id, QUESTION_TEMPLATE_FONDS_PROPRES, prompt=PROMPT_TEMPLATE_FONDS_PROPRES)
    df_fonds_propres = parse_fonds_propres_text(fonds_propres_response)
    df_fonds_propres['Société'] = societe
    
    # Extraction du détail du SCR
    scr_detail_response = chat_with_pdf(source_id, QUESTION_TEMPLATE_SCR_DETAIL, prompt=PROMPT_TEMPLATE_SCR_DETAIL)
    df_scr_detail = parse_scr_detail_text(scr_detail_response)
    df_scr_detail['Société'] = societe
    
    # Extraction des actifs
    actifs_response = chat_with_pdf(source_id, QUESTION_TEMPLATE_ACTIFS, prompt=PROMPT_TEMPLATE_ACTIFS)
    df_actifs = parse_actifs_text(actifs_response)
    df_actifs['Société'] = societe
    
    # Fusionner les résultats
    try:
        df = pd.merge(df_base, df_fonds_propres, on='Société', how='outer')
        df = pd.merge(df, df_scr_detail, on='Société', how='outer')
        df = pd.merge(df, df_actifs, on='Société', how='outer')
    except KeyError as e:
        st.warning(f"Erreur lors de la fusion des données pour {pdf_name}: {e}")
        
        # Créer un DataFrame combiné avec toutes les colonnes
        df = pd.DataFrame({
            'Société': [societe],
            'SCR (€)': [df_base['SCR (€)'].iloc[0] if not df_base.empty else np.nan],
            'MCR (€)': [df_base['MCR (€)'].iloc[0] if not df_base.empty else np.nan],
            'Ratio de solvabilité (%)': [df_base['Ratio de solvabilité (%)'].iloc[0] if not df_base.empty else np.nan],
            'Éléments éligibles (€)': [df_fonds_propres['Éléments éligibles (€)'].iloc[0] if not df_fonds_propres.empty else np.nan],
            'Capital et primes (€)': [df_fonds_propres['Capital et primes (€)'].iloc[0] if not df_fonds_propres.empty else np.nan],
            'Réserve de réconciliation (€)': [df_fonds_propres['Réserve de réconciliation (€)'].iloc[0] if not df_fonds_propres.empty else np.nan],
            'Dettes subordonnées (€)': [df_fonds_propres['Dettes subordonnées (€)'].iloc[0] if not df_fonds_propres.empty else np.nan],
            'Fonds excédentaires (€)': [df_fonds_propres['Fonds excédentaires (€)'].iloc[0] if not df_fonds_propres.empty else np.nan],
            'SCR Risque de Marché (€)': [df_scr_detail['SCR Risque de Marché (€)'].iloc[0] if not df_scr_detail.empty else np.nan],
            'SCR Risque de Contrepartie (€)': [df_scr_detail['SCR Risque de Contrepartie (€)'].iloc[0] if not df_scr_detail.empty else np.nan],
            'SCR Risque de Souscription Vie (€)': [df_scr_detail['SCR Risque de Souscription Vie (€)'].iloc[0] if not df_scr_detail.empty else np.nan],
            'SCR Risque de Souscription Santé (€)': [df_scr_detail['SCR Risque de Souscription Santé (€)'].iloc[0] if not df_scr_detail.empty else np.nan],
            'SCR Risque de Souscription Non-Vie (€)': [df_scr_detail['SCR Risque de Souscription Non-Vie (€)'].iloc[0] if not df_scr_detail.empty else np.nan],
            'SCR Risque Opérationnel (€)': [df_scr_detail['SCR Risque Opérationnel (€)'].iloc[0] if not df_scr_detail.empty else np.nan],
            'Effet de Diversification (€)': [df_scr_detail['Effet de Diversification (€)'].iloc[0] if not df_scr_detail.empty else np.nan],
            'Obligations (€)': [df_actifs['Obligations (€)'].iloc[0] if not df_actifs.empty else np.nan],
            'Actions (€)': [df_actifs['Actions (€)'].iloc[0] if not df_actifs.empty else np.nan],
            'Fonds d\'investissement (€)': [df_actifs['Fonds d\'investissement (€)'].iloc[0] if not df_actifs.empty else np.nan],
            'Produits dérivés (€)': [df_actifs['Produits dérivés (€)'].iloc[0] if not df_actifs.empty else np.nan],
            'Immobilier (€)': [df_actifs['Immobilier (€)'].iloc[0] if not df_actifs.empty else np.nan],
            'Trésorerie et dépôts (€)': [df_actifs['Trésorerie et dépôts (€)'].iloc[0] if not df_actifs.empty else np.nan],
            'Participations (€)': [df_actifs['Participations (€)'].iloc[0] if not df_actifs.empty else np.nan],
            'Autres actifs (€)': [df_actifs['Autres actifs (€)'].iloc[0] if not df_actifs.empty else np.nan],
            'Total des actifs (€)': [df_actifs['Total des actifs (€)'].iloc[0] if not df_actifs.empty else np.nan]
        })
    
    return df

def main():
    """
    Fonction principale de l'application Streamlit.
    Gère l'interface utilisateur, le chargement des PDFs, l'extraction des données,
    et l'affichage des résultats sous forme de tableaux et de graphiques.
    """
    st.title("📊 Analyse de rapports SFCR")
    st.markdown("""
    ### Instructions
    - Chargez un ou plusieurs fichiers PDF
    - Pour un seul PDF : visualisation simple des données extraites
    - Pour plusieurs PDFs : comparaison automatique avec graphiques et statistiques
    - Possibilité de télécharger les données et graphiques au format XLSX
    """)

    if st.sidebar.button("Recharger les données PDFs"):
        st.session_state.pdf_data = {}
        st.success("Les données PDFs ont été réinitialisées.")
    
    st.sidebar.subheader("Chargement de PDFs")
    uploaded_files = st.sidebar.file_uploader("Télécharger vos fichiers .pdf", type="pdf", accept_multiple_files=True)

    if "pdf_data" not in st.session_state:
        st.session_state.pdf_data = {}
    
    prompt = PROMPT_TEMPLATE_BASE
    question = QUESTION_TEMPLATE_BASE

    if uploaded_files:
        progress_placeholder = st.empty()
        for pdf_file in uploaded_files:
            if pdf_file.name not in st.session_state.pdf_data:
                progress_placeholder.info(f"Traitement du fichier : {pdf_file.name}")
                with st.spinner(f"Traitement en cours..."):
                    source_id = add_pdf_from_file(pdf_file)
                    if source_id:
                        df_pdf = process_pdf_unified(source_id, pdf_file.name)
                        
                        if not df_pdf.empty:
                            st.session_state.pdf_data[pdf_file.name] = df_pdf
                            progress_placeholder.empty()
                        else:
                            progress_placeholder.error(f"Aucune donnée extraite pour {pdf_file.name}")
                    else:
                        progress_placeholder.error(f"Erreur lors de l'obtention du source_id pour {pdf_file.name}")
        
        if any(pdf_file.name not in st.session_state.pdf_data for pdf_file in uploaded_files):
            st.success("Traitement des fichiers terminé !")

    if st.session_state.pdf_data:
        nb_pdfs = len(st.session_state.pdf_data)
        main_tabs = st.tabs(["Question", "Analyse"])
        
        with main_tabs[0]:
            st.subheader("Question sur le document")
            selected_pdf = st.selectbox(
                "Sélectionner un PDF",
                list(st.session_state.pdf_data.keys())
            )

            if 'user_question' not in st.session_state:
                st.session_state.user_question = ""

            col1, col2 = st.columns(2)
            predefined_prompts = get_predefined_prompts()
            
            with col1:
                if st.button("Analyse du SCR"):
                    st.session_state.user_question = predefined_prompts["Analyse du SCR"]
                if st.button("Analyse des fonds propres"):
                    st.session_state.user_question = predefined_prompts["Analyse des fonds propres"]
                if st.button("Analyse des actifs"):
                    st.session_state.user_question = predefined_prompts["Analyse des actifs"]
            
            with col2:
                if st.button("Analyse du ratio de solvabilité"):
                    st.session_state.user_question = predefined_prompts["Analyse du ratio de solvabilité"]
                if st.button("Analyse du MCR"):
                    st.session_state.user_question = predefined_prompts["Analyse du MCR"]

            user_question = st.text_area(
                "Poser votre question sur le PDF",
                value=st.session_state.user_question,
                height=100,
                key="question_input"
            )
            
            if st.button("Valider la question"):
                if user_question:
                    with st.spinner("Traitement de votre question..."):
                        pdf_file = [f for f in uploaded_files if f.name == selected_pdf][0]
                        source_id = add_pdf_from_file(pdf_file)
                        
                        if source_id:
                            response = chat_with_pdf(source_id, user_question)
                            if response:
                                st.write("Réponse :")
                                st.write(response)
                            else:
                                st.error("Désolé, je n'ai pas pu obtenir de réponse.")
                        else:
                            st.error("Erreur lors de l'accès au PDF.")
                else:
                    st.warning("Veuillez entrer une question.")

        with main_tabs[1]:
            if nb_pdfs == 1:
                pdf_name = list(st.session_state.pdf_data.keys())[0]
                df_selected = st.session_state.pdf_data[pdf_name]
                st.subheader(f"Données extraites pour : {pdf_name}")
                display_data(df_selected, show_full_analysis=False)
            else:
                selected_pdfs = st.sidebar.multiselect(
                    "Sélectionnez les PDFs à comparer",
                    list(st.session_state.pdf_data.keys()),
                    default=list(st.session_state.pdf_data.keys())
                )
                
                if selected_pdfs:
                    dfs_to_combine = []
                    for name in selected_pdfs:
                        df = st.session_state.pdf_data[name].copy()
                        dfs_to_combine.append(df)
                    
                    combined_df = pd.concat(dfs_to_combine, ignore_index=True)
                    
                    moyenne = pd.DataFrame({
                        'Société': ['Moyenne'],
                        'SCR (€)': [round(combined_df['SCR (€)'].mean(), 2)],
                        'MCR (€)': [round(combined_df['MCR (€)'].mean(), 2)],
                        'Éléments éligibles (€)': [round(combined_df['Éléments éligibles (€)'].mean(), 2)],
                        'Réserve de réconciliation (€)': [round(combined_df['Réserve de réconciliation (€)'].mean(), 2)],
                        'Dettes subordonnées (€)': [round(combined_df['Dettes subordonnées (€)'].mean(), 2)],
                        'Fonds excédentaires (€)': [round(combined_df['Fonds excédentaires (€)'].mean(), 2)],
                        'Capital et primes (€)': [round(combined_df['Capital et primes (€)'].mean(), 2)],
                        'Ratio de solvabilité (%)': [round(combined_df['Ratio de solvabilité (%)'].mean(), 2)],
                        'SCR Risque de Marché (€)': [round(combined_df['SCR Risque de Marché (€)'].mean(), 2)],
                        'SCR Risque de Contrepartie (€)': [round(combined_df['SCR Risque de Contrepartie (€)'].mean(), 2)],
                        'SCR Risque de Souscription Vie (€)': [round(combined_df['SCR Risque de Souscription Vie (€)'].mean(), 2)],
                        'SCR Risque de Souscription Santé (€)': [round(combined_df['SCR Risque de Souscription Santé (€)'].mean(), 2)],
                        'SCR Risque de Souscription Non-Vie (€)': [round(combined_df['SCR Risque de Souscription Non-Vie (€)'].mean(), 2)],
                        'SCR Risque Opérationnel (€)': [round(combined_df['SCR Risque Opérationnel (€)'].mean(), 2)],
                        'Effet de Diversification (€)': [round(combined_df['Effet de Diversification (€)'].mean(), 2)],
                        'Obligations (€)': [round(combined_df['Obligations (€)'].mean(), 2)],
                        'Actions (€)': [round(combined_df['Actions (€)'].mean(), 2)],
                        'Fonds d\'investissement (€)': [round(combined_df['Fonds d\'investissement (€)'].mean(), 2)],
                        'Produits dérivés (€)': [round(combined_df['Produits dérivés (€)'].mean(), 2)],
                        'Immobilier (€)': [round(combined_df['Immobilier (€)'].mean(), 2)],
                        'Trésorerie et dépôts (€)': [round(combined_df['Trésorerie et dépôts (€)'].mean(), 2)],
                        'Participations (€)': [round(combined_df['Participations (€)'].mean(), 2)],
                        'Autres actifs (€)': [round(combined_df['Autres actifs (€)'].mean(), 2)],
                        'Total des actifs (€)': [round(combined_df['Total des actifs (€)'].mean(), 2)]
                    })

                    display_df = pd.concat([combined_df, moyenne], ignore_index=True)
                    
                    download_excel(display_df, filename="analyse_sfcr.xlsx")
                    st.subheader("Comparaison entre PDFs")
                    
                    columns_to_display = [
                        'Société', 'SCR (€)', 'MCR (€)', 'Éléments éligibles (€)', 
                        'Capital et primes (€)', 'Réserve de réconciliation (€)', 
                        'Dettes subordonnées (€)', 'Fonds excédentaires (€)', 
                        'Ratio de solvabilité (%)'
                    ]
                    
                    display_df_transposed = display_df[columns_to_display].set_index('Société').transpose()
                    display_df_transposed.index.name = 'Métrique'
                    display_df_transposed = display_df_transposed.reset_index()
                    st.dataframe(display_df_transposed)

                    metric_tabs = st.tabs([
                        "SCR", "MCR", "Éléments éligibles", "Réserve de réconciliation", 
                        "Dettes subordonnées", "Fonds excédentaires", "Capital et primes", 
                        "Ratio de solvabilité", "Détail du SCR", "Actifs"
                    ])

                    with metric_tabs[0]:  # SCR
                        fig_scr = create_matplotlib_figure(
                            combined_df,
                            "SCR par PDF", 
                            "Société", 
                            "SCR (€)", 
                            'skyblue',
                            moyenne=moyenne['SCR (€)'].values[0]
                        )
                        st.pyplot(fig_scr)

                    with metric_tabs[1]:  # MCR
                        fig_mcr = create_matplotlib_figure(
                            combined_df,
                            "MCR par PDF", 
                            "Société", 
                            "MCR (€)", 
                            'lightgreen',
                            moyenne=moyenne['MCR (€)'].values[0]
                        )
                        st.pyplot(fig_mcr)

                    with metric_tabs[2]:  # Éléments éligibles
                        fig_eof = create_matplotlib_figure(
                            combined_df,
                            "Éléments éligibles par PDF",
                            "Société", 
                            "Éléments éligibles (€)",
                            'orange',
                            moyenne=moyenne['Éléments éligibles (€)'].values[0]
                        )
                        st.pyplot(fig_eof)

                    with metric_tabs[3]:  # Réserve de réconciliation
                        fig_reserve = create_matplotlib_figure(
                            combined_df,
                            "Réserve de réconciliation par PDF",
                            "Société", 
                            "Réserve de réconciliation (€)",
                            'purple',
                            moyenne=moyenne['Réserve de réconciliation (€)'].values[0]
                        )
                        st.pyplot(fig_reserve)

                    with metric_tabs[4]:  # Dettes subordonnées
                        fig_dettes = create_matplotlib_figure(
                            combined_df,
                            "Dettes subordonnées par PDF",
                            "Société", 
                            "Dettes subordonnées (€)",
                            'lightgreen',
                            moyenne=moyenne['Dettes subordonnées (€)'].values[0]
                        )
                        st.pyplot(fig_dettes)

                    with metric_tabs[5]:  # Fonds excédentaires
                        fig_fonds = create_matplotlib_figure(
                            combined_df,
                            "Fonds excédentaires par PDF",
                            "Société", 
                            "Fonds excédentaires (€)",
                            'lightcoral',
                            moyenne=moyenne['Fonds excédentaires (€)'].values[0]
                        )
                        st.pyplot(fig_fonds)

                    with metric_tabs[6]:  # Capital et primes
                        fig_capital = create_matplotlib_figure(
                            combined_df,
                            "Capital et primes par PDF",
                            "Société", 
                            "Capital et primes (€)",
                            'lightblue',
                            moyenne=moyenne['Capital et primes (€)'].values[0]
                        )
                        st.pyplot(fig_capital)

                    with metric_tabs[7]:  # Ratio de solvabilité
                        fig_ratio = create_matplotlib_figure(
                            combined_df,
                            "Ratio de solvabilité par PDF", 
                            "Société", 
                            "Ratio de solvabilité (%)", 
                            'plum',
                            moyenne=moyenne['Ratio de solvabilité (%)'].values[0]
                        )
                        st.pyplot(fig_ratio)
                        
                    with metric_tabs[8]:  # Détail du SCR
                        st.subheader("Détail du SCR par société")
                        selected_company = st.selectbox(
                            "Sélectionnez une société pour voir la répartition de son SCR",
                            combined_df['Société'].tolist()
                        )
                        
                        col1, col2 = st.columns(2)
                        
                        with col1:
                            pie_chart = create_scr_pie_chart(combined_df, selected_company)
                            if pie_chart:
                                st.pyplot(pie_chart)
                            else:
                                st.info("Données insuffisantes pour créer le graphique en camembert.")
                        
                        with col2:
                            waterfall_chart = create_scr_waterfall_chart(combined_df, selected_company)
                            if waterfall_chart:
                                st.pyplot(waterfall_chart)
                            else:
                                st.info("Données insuffisantes pour créer le graphique en cascade.")
                        
                        st.subheader("Composantes du SCR par société")
                        scr_components_df = combined_df[['Société', 'SCR (€)', 'SCR Risque de Marché (€)', 
                                                        'SCR Risque de Contrepartie (€)', 'SCR Risque de Souscription Vie (€)',
                                                        'SCR Risque de Souscription Santé (€)', 'SCR Risque de Souscription Non-Vie (€)',
                                                        'SCR Risque Opérationnel (€)', 'Effet de Diversification (€)']]
                        scr_components_transposed = scr_components_df.set_index('Société').transpose()
                        scr_components_transposed.index.name = 'Composante SCR'
                        scr_components_transposed = scr_components_transposed.reset_index()
                        st.dataframe(scr_components_transposed)

                    with metric_tabs[9]:  # Actifs
                        st.subheader("Actifs par société")
                        actifs_df = combined_df[['Société', 'Total des actifs (€)', 'Obligations (€)', 'Actions (€)', 
                                                 'Fonds d\'investissement (€)', 'Produits dérivés (€)', 'Immobilier (€)', 
                                                 'Trésorerie et dépôts (€)', 'Participations (€)', 'Autres actifs (€)']]
                        actifs_df_transposed = actifs_df.set_index('Société').transpose()
                        actifs_df_transposed.index.name = 'Composante Actifs'
                        actifs_df_transposed = actifs_df_transposed.reset_index()
                        st.dataframe(actifs_df_transposed)

                        fig_total_actifs = create_matplotlib_figure(
                            combined_df,
                            "Total des actifs par société",
                            "Société", 
                            "Total des actifs (€)",
                            'darkgreen',
                            moyenne=moyenne['Total des actifs (€)'].values[0]
                        )
                        st.pyplot(fig_total_actifs)
                else:
                    st.info("Veuillez sélectionner au moins un PDF pour la comparaison.")

if __name__ == "__main__":
    main()
