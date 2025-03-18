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

API_KEY = "sec_0CXaT5eGzNtGSDTkETkwTSJbyPdWAbJN"

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

def parse_base_text(text):
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
    # Patterns plus flexibles pour capturer différents formats
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
    
    # Fonction pour convertir les valeurs en fonction de l'unité
    def convert_value(value_str, unit_pattern):
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
    
    # Chercher les patterns standards
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
    
    # Chercher les patterns alternatifs (milliards)
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
    
    # Chercher les patterns pour millions
    for key, pattern in million_patterns.items():
        column_name = column_mapping[key]
        
        if pd.isna(current_entry[column_name]):
            match = re.search(pattern, text)
            if match:
                value_str = match.group(1)
                unit_pattern = match.group(0)
                value = convert_value(value_str, unit_pattern)
                current_entry[column_name] = value
    
    # Recherche spécifique pour les valeurs numériques dans le texte
    if pd.isna(current_entry['Éléments éligibles (€)']):
        match = re.search(r"Éléments éligibles.*?(\d[\d\s,\.]+)(?:€|Md€|M€)", text, re.IGNORECASE)
        if match:
            value_str = match.group(1)
            unit_pattern = match.group(0)
            current_entry['Éléments éligibles (€)'] = convert_value(value_str, unit_pattern)
    
    data.append(current_entry)
    return pd.DataFrame(data)

def add_pdf_from_file(uploaded_file):
    url = "https://api.chatpdf.com/v1/sources/add-file"
    headers = {"x-api-key": API_KEY}
    files = {"file": (uploaded_file.name, uploaded_file, "application/pdf")}
    
    try:
        response = requests.post(url, files=files, headers=headers)
        response.raise_for_status()
        return response.json()["sourceId"]
    except requests.exceptions.RequestException as e:
        st.error(f"Erreur lors de l'ajout du fichier : {e}")
        if e.response is not None:
            st.error(f"Réponse du serveur : {e.response.text}")
        return None

def chat_with_pdf(source_id, question, prompt=None):
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
    for col in ["SCR (€)", "MCR (€)", "Solvency Ratio (%)"]:
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
    st.subheader("Aperçu des données")
    st.dataframe(df_solvency)

    if show_full_analysis:
        st.subheader("Métriques clés")
        col1, col2, col3 = st.columns(3)
        col1.metric("Nombre de sociétés", len(df_solvency))
        col2.metric("SCR moyen (€)", f"{df_solvency['SCR (€)'].mean():,.2f} €")
        col3.metric("Ratio de solvabilité moyen (%)", f"{df_solvency['Solvency Ratio (%)'].mean():.2f} %")

        st.subheader("Statistiques supplémentaires")
        stats_df = compute_additional_statistics(df_solvency)
        st.dataframe(stats_df)

        st.subheader("Graphique statique")
        option = st.selectbox("Choisissez une visualisation statique", ("SCR (€)", "MCR (€)", "Solvency Ratio (%)"))
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
            ax.bar(df_solvency["Société"], df_solvency["Solvency Ratio (%)"].fillna(0), color='lightgreen')
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
        metric = st.selectbox("Sélectionnez la métrique", ("SCR (€)", "MCR (€)", "Solvency Ratio (%)"))
        display_altair_chart(df_solvency, metric, chart_type, color)

def download_excel(df, filename="analyse_sfcr.xlsx"):
    buffer = BytesIO()
    try:
        with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
            df_donnees = df[df['Société'] != 'Moyenne'].copy()
            
            # Onglet avec les données brutes
            df_donnees.to_excel(writer, sheet_name="Données brutes", index=False)
            
            # Calculer les statistiques
            stats_data = {
                'Métrique': ['Moyenne', 'Médiane', 'Écart-type', 'Minimum', 'Maximum'],
                'SCR (€)': [
                    df_donnees['SCR (€)'].mean(),
                    df_donnees['SCR (€)'].median(),
                    df_donnees['SCR (€)'].std(),
                    df_donnees['SCR (€)'].min(),
                    df_donnees['SCR (€)'].max()
                ],
                'MCR (€)': [
                    df_donnees['MCR (€)'].mean(),
                    df_donnees['MCR (€)'].median(),
                    df_donnees['MCR (€)'].std(),
                    df_donnees['MCR (€)'].min(),
                    df_donnees['MCR (€)'].max()
                ],
                'Éléments éligibles (€)': [
                    df_donnees['Éléments éligibles (€)'].mean(),
                    df_donnees['Éléments éligibles (€)'].median(),
                    df_donnees['Éléments éligibles (€)'].std(),
                    df_donnees['Éléments éligibles (€)'].min(),
                    df_donnees['Éléments éligibles (€)'].max()
                ],
                'Capital et primes (€)': [
                    df_donnees['Capital et primes (€)'].mean(),
                    df_donnees['Capital et primes (€)'].median(),
                    df_donnees['Capital et primes (€)'].std(),
                    df_donnees['Capital et primes (€)'].min(),
                    df_donnees['Capital et primes (€)'].max()
                ],
                'Réserve de réconciliation (€)': [
                    df_donnees['Réserve de réconciliation (€)'].mean(),
                    df_donnees['Réserve de réconciliation (€)'].median(),
                    df_donnees['Réserve de réconciliation (€)'].std(),
                    df_donnees['Réserve de réconciliation (€)'].min(),
                    df_donnees['Réserve de réconciliation (€)'].max()
                ],
                'Dettes subordonnées (€)': [
                    df_donnees['Dettes subordonnées (€)'].mean(),
                    df_donnees['Dettes subordonnées (€)'].median(),
                    df_donnees['Dettes subordonnées (€)'].std(),
                    df_donnees['Dettes subordonnées (€)'].min(),
                    df_donnees['Dettes subordonnées (€)'].max()
                ],
                'Fonds excédentaires (€)': [
                    df_donnees['Fonds excédentaires (€)'].mean(),
                    df_donnees['Fonds excédentaires (€)'].median(),
                    df_donnees['Fonds excédentaires (€)'].std(),
                    df_donnees['Fonds excédentaires (€)'].min(),
                    df_donnees['Fonds excédentaires (€)'].max()
                ],
                'Ratio de solvabilité (%)': [
                    df_donnees['Ratio de solvabilité (%)'].mean(),
                    df_donnees['Ratio de solvabilité (%)'].median(),
                    df_donnees['Ratio de solvabilité (%)'].std(),
                    df_donnees['Ratio de solvabilité (%)'].min(),
                    df_donnees['Ratio de solvabilité (%)'].max()
                ]
            }
            stats_df = pd.DataFrame(stats_data)
            
            # Ajouter les statistiques en dessous des données brutes
            workbook = writer.book
            worksheet = writer.sheets['Données brutes']
            
            # Masquer le quadrillage pour toute la feuille
            worksheet.sheet_view.showGridLines = False
            
            # Déterminer la ligne où commencer à écrire les statistiques
            start_row = len(df_donnees) + 3
            
            # Écrire un titre pour la section statistiques
            worksheet.cell(row=start_row, column=1, value="STATISTIQUES")
            worksheet.cell(row=start_row, column=1).font = openpyxl.styles.Font(bold=True, size=14)
            
            # Écrire les en-têtes des colonnes pour les statistiques
            for j, col in enumerate(stats_df.columns):
                cell = worksheet.cell(row=start_row + 1, column=j + 1)
                cell.value = col
                cell.font = openpyxl.styles.Font(bold=True)
                cell.fill = openpyxl.styles.PatternFill(start_color="E0E0E0", end_color="E0E0E0", fill_type="solid")
                cell.border = openpyxl.styles.Border(
                    bottom=openpyxl.styles.Side(style='thin'),
                    top=openpyxl.styles.Side(style='thin'),
                    left=openpyxl.styles.Side(style='thin'),
                    right=openpyxl.styles.Side(style='thin')
                )
            
            # Écrire les statistiques
            for i, row in enumerate(stats_df.values):
                for j, value in enumerate(row):
                    cell = worksheet.cell(row=start_row + 2 + i, column=j + 1)
                    if j == 0:  # Première colonne (Métrique)
                        cell.value = value
                        cell.font = openpyxl.styles.Font(bold=True)
                    else:  # Colonnes de données
                        if isinstance(value, (int, float)):
                            if j == 8:  # Ratio de solvabilité (%)
                                cell.value = value
                                cell.number_format = '0.00"%"'
                            else:
                                cell.value = value
                                cell.number_format = '#,##0.00'
                        else:
                            cell.value = value
                    
                    # Ajouter des bordures à toutes les cellules des statistiques
                    cell.border = openpyxl.styles.Border(
                        left=openpyxl.styles.Side(style='thin'),
                        right=openpyxl.styles.Side(style='thin'),
                        bottom=openpyxl.styles.Side(style='thin'),
                        top=openpyxl.styles.Side(style='thin')
                    )
            
            # Ajouter des bordures aux données brutes
            for row_idx in range(1, len(df_donnees) + 2):
                for col_idx in range(1, len(df_donnees.columns) + 1):
                    cell = worksheet.cell(row=row_idx, column=col_idx)
                    cell.border = openpyxl.styles.Border(
                        left=openpyxl.styles.Side(style='thin'),
                        right=openpyxl.styles.Side(style='thin'),
                        bottom=openpyxl.styles.Side(style='thin'),
                        top=openpyxl.styles.Side(style='thin')
                    )
                    
                    # Mettre en forme les en-têtes des colonnes
                    if row_idx == 1:
                        cell.font = openpyxl.styles.Font(bold=True)
                        cell.fill = openpyxl.styles.PatternFill(start_color="E0E0E0", end_color="E0E0E0", fill_type="solid")
            
            # Ajouter une feuille "Fonds propres"
            fonds_propres_columns = [
                'Société', 
                'Éléments éligibles (€)', 
                'SCR (€)', 
                'Capital et primes (€)', 
                'Réserve de réconciliation (€)', 
                'Dettes subordonnées (€)', 
                'Fonds excédentaires (€)'
            ]
            
            # Créer un DataFrame pour la feuille Fonds propres
            fonds_propres_df = df_donnees[fonds_propres_columns].copy()
            
            # Trier par Éléments éligibles décroissants
            fonds_propres_df = fonds_propres_df.sort_values(by='Éléments éligibles (€)', ascending=False)
            
            # Écrire dans une nouvelle feuille
            fonds_propres_df.to_excel(writer, sheet_name="Fonds propres", index=False)
            
            # Formater la feuille Fonds propres
            worksheet = writer.sheets['Fonds propres']
            
            # Masquer le quadrillage
            worksheet.sheet_view.showGridLines = False
            
            # Formater les en-têtes de colonnes
            for col_num, column_title in enumerate(fonds_propres_columns, 1):
                cell = worksheet.cell(row=1, column=col_num)
                cell.font = openpyxl.styles.Font(bold=True)
                cell.alignment = openpyxl.styles.Alignment(horizontal='center')
                cell.fill = openpyxl.styles.PatternFill(start_color="E0E0E0", end_color="E0E0E0", fill_type="solid")
                cell.border = openpyxl.styles.Border(
                    bottom=openpyxl.styles.Side(style='thin'),
                    top=openpyxl.styles.Side(style='thin'),
                    left=openpyxl.styles.Side(style='thin'),
                    right=openpyxl.styles.Side(style='thin')
                )
                
            # Formater les valeurs numériques
            for row_idx in range(2, len(fonds_propres_df) + 2):
                for col_idx in range(1, len(fonds_propres_columns) + 1):
                    cell = worksheet.cell(row=row_idx, column=col_idx)
                    
                    # Appliquer le format numérique aux colonnes de données
                    if col_idx > 1:
                        cell.number_format = '#,##0.00'
                    
                    # Ajouter des bordures à toutes les cellules
                    cell.border = openpyxl.styles.Border(
                        left=openpyxl.styles.Side(style='thin'),
                        right=openpyxl.styles.Side(style='thin'),
                        bottom=openpyxl.styles.Side(style='thin'),
                        top=openpyxl.styles.Side(style='thin')
                    )
            
            # Ajuster la largeur des colonnes dans les deux feuilles
            for sheet_name in ["Données brutes", "Fonds propres"]:
                worksheet = writer.sheets[sheet_name]
                for column in worksheet.columns:
                    max_length = 0
                    column_letter = column[0].column_letter
                    for cell in column:
                        try:
                            if len(str(cell.value)) > max_length:
                                max_length = len(str(cell.value))
                        except:
                            pass
                    adjusted_width = (max_length + 2)
                    worksheet.column_dimensions[column_letter].width = adjusted_width

        buffer.seek(0)
        st.download_button(
            label="📥 Télécharger les données (XLSX)",
            data=buffer,
            file_name=filename,
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
    except Exception as e:
        st.error(f"Erreur lors de la création du fichier Excel : {e}")

def create_matplotlib_figure(data, title, x_label, y_label, color='steelblue', moyenne=None):
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

def get_predefined_prompts():
    return {
        "Analyse du SCR": "Analyse en détail la composition du SCR. Donne la répartition des différents modules de risques (marché, souscription, etc.) et leurs montants, attention à bien convertir les montants qui peuvent être en millions d'euros. Explique quels sont les risques principaux.",
        "Analyse des fonds propres": "Analyse la composition des fonds propres. Détaille les différents tiers (Tier 1, 2, 3) et leur montant (attention à bien convertir si en millions d'euros). Compare avec l'année précédente si disponible et explique l'évolution.",
        "Analyse du ratio de solvabilité": "Explique le ratio de solvabilité actuel et son évolution. Compare avec l'année précédente et explique les facteurs qui ont influencé ce ratio. Précise si des mesures particulières ont été prises pour maintenir ou améliorer ce ratio.",
        "Analyse du MCR": "Donne les détails sur le MCR (Minimum Capital Requirement). Précise son montant (attention à bien convertir si en millions d'euros), explique son calcul et son évolution par rapport à l'année précédente."
    }

def process_pdf_unified(source_id, pdf_name):
    base_response = chat_with_pdf(source_id, QUESTION_TEMPLATE_BASE, prompt=PROMPT_TEMPLATE_BASE)
    df_base = parse_base_text(base_response)
    
    # Vérifie si df_base est vide ou si la colonne 'Société' est manquante
    if df_base.empty or 'Société' not in df_base.columns:
        df_base = pd.DataFrame({
            'Société': [f"Société inconnue ({pdf_name})"],
            'SCR (€)': [np.nan],
            'MCR (€)': [np.nan],
            'Ratio de solvabilité (%)': [np.nan]
        })
    
    societe = df_base['Société'].iloc[0] if not df_base.empty else f"Société inconnue ({pdf_name})"
    
    fonds_propres_response = chat_with_pdf(source_id, QUESTION_TEMPLATE_FONDS_PROPRES, prompt=PROMPT_TEMPLATE_FONDS_PROPRES)
    df_fonds_propres = parse_fonds_propres_text(fonds_propres_response)
    df_fonds_propres['Société'] = societe
    
    column_mapping = {
        'Éléments éligibles (€)': 'Éléments éligibles (€)',
        'Capital et primes (€)': 'Capital et primes (€)',
        'Réserve de réconciliation (€)': 'Réserve de réconciliation (€)',
        'Dettes subordonnées (€)': 'Dettes subordonnées (€)',
        'Fonds excédentaires (€)': 'Fonds excédentaires (€)'
    }
    
    df_fonds_propres = df_fonds_propres.rename(columns=column_mapping)
    
    for col in column_mapping.values():
        if col not in df_fonds_propres.columns:
            df_fonds_propres[col] = np.nan
    
    # Fusionner les résultats
    try:
        df = pd.merge(df_base, df_fonds_propres, on='Société', how='outer')
    except KeyError as e:
        # En cas d'erreur, créer un DataFrame combiné manuellement
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
            'Fonds excédentaires (€)': [df_fonds_propres['Fonds excédentaires (€)'].iloc[0] if not df_fonds_propres.empty else np.nan]
        })
    
    return df

def extract_amount(text):
    # Extraire un montant d'une réponse textuelle
    # Chercher d'abord un montant avec le symbole €
    amount_pattern = r"(\d[\d\s]+(?:,\d+)?)\s*(?:€|euros)"
    match = re.search(amount_pattern, text)
    if match:
        amount_str = match.group(1).replace(" ", "").replace(",", ".")
        try:
            return float(amount_str)
        except ValueError:
            return np.nan
    
    # Chercher un montant avec "millions" ou "M€"
    million_pattern = r"(\d[\d\s]*(?:,\d+)?)\s*(?:millions|million|M)(?:\s*d['']\s*euros|\s*€)?"
    match = re.search(million_pattern, text)
    if match:
        amount_str = match.group(1).replace(" ", "").replace(",", ".")
        try:
            return float(amount_str) * 1_000_000
        except ValueError:
            return np.nan
    
    return np.nan

def main():
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
                        # Utiliser process_pdf_unified pour tous les PDFs sans condition
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
                    # Créer une liste pour stocker les DataFrames 
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
                        'Ratio de solvabilité (%)': [round(combined_df['Ratio de solvabilité (%)'].mean(), 2)]
                    })

                    display_df = pd.concat([combined_df, moyenne], ignore_index=True)
                    
                    download_excel(display_df, filename="analyse_sfcr.xlsx")
                    st.subheader("Comparaison entre PDFs")
                    
                    # Définir les colonnes à afficher dans l'ordre souhaité (sans PDF)
                    columns_to_display = [
                        'Société', 'SCR (€)', 'MCR (€)', 'Éléments éligibles (€)', 
                        'Capital et primes (€)', 'Réserve de réconciliation (€)', 
                        'Dettes subordonnées (€)', 'Fonds excédentaires (€)', 
                        'Ratio de solvabilité (%)'
                    ]
                    
                    # Afficher le tableau avec toutes les colonnes dans l'ordre défini
                    st.dataframe(display_df[columns_to_display])

                    # Après la définition des onglets existants, ajoutez des onglets pour les nouvelles métriques
                    metric_tabs = st.tabs([
                        "SCR", "MCR", "Éléments éligibles", "Réserve de réconciliation", 
                        "Dettes subordonnées", "Fonds excédentaires", "Capital et primes", "Ratio de solvabilité"
                    ])

                    # Puis ajoutez les visualisations pour les nouvelles métriques
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

                    # Ajoutons les visualisations pour les onglets manquants
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
                else:
                    st.info("Veuillez sélectionner au moins un PDF pour la comparaison.")

if __name__ == "__main__":
    main()
