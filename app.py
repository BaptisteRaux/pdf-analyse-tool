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

API_KEY = "***REMOVED***"

PROMPT_TEMPLATE = """
Donne les réponses sous cette forme SCR : X, MCR : X , Ratio de solvabilité : X, 
Le SCR est un montant en euros. Convertis les valeurs en nombres sans abréviation : 
par exemple, écris '13 300 000 000€' au lieu de '13,3 Md€'. 
Ne laisse aucune lettre pour désigner les millions ou milliards, uniquement le nombre complet en euros.
"""

QUESTION_TEMPLATE = """
0) Nom de la société : 
1) Donne le SCR 
2) Donne le MCR 
3) Donne le ratio de solvabilité, également appelé le taux de couverture
"""

def parse_solvency_text(text):
    patterns = {
        'company': r"0\)\s*Nom de la société\s*:\s*(.+)",
        'scr': r"1\)\s*SCR\s*:\s*([\d\s]+)€",
        'mcr': r"2\)\s*MCR\s*:\s*([\d\s]+)€",
        'ratio': r"3\)\s*Ratio de solvabilité\s*:\s*([\d,\.]+)\s*%"
    }
    data = []
    current_entry = {'Société': None, 'SCR (€)': np.nan, 'MCR (€)': np.nan, 'Ratio de solvabilité (%)': np.nan}
    
    for line in text.splitlines():
        for key, pattern in patterns.items():
            match = re.search(pattern, line)
            if match:
                if key == 'company':
                    if current_entry['Société'] is not None:
                        data.append(current_entry.copy())
                    current_entry = {'Société': match.group(1).strip(), 'SCR (€)': np.nan, 'MCR (€)': np.nan, 'Ratio de solvabilité (%)': np.nan}
                elif key == 'scr':
                    current_entry['SCR (€)'] = int(match.group(1).replace(" ", ""))
                elif key == 'mcr':
                    current_entry['MCR (€)'] = int(match.group(1).replace(" ", ""))
                elif key == 'ratio':
                    current_entry['Ratio de solvabilité (%)'] = float(match.group(1).replace(",", "."))
    
    if current_entry['Société'] is not None:
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
        return response.json()["content"]
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


def download_excel(df, filename="comparaison.xlsx"):
    buffer = BytesIO()
    with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
        df_data = df[df['Société'] != 'Moyenne'].copy()

        stats = pd.DataFrame({
            'Statistique': ['Moyenne', 'Médiane', 'Minimum', 'Maximum'],
            'SCR (€)': [
                df_data['SCR (€)'].mean(),
                df_data['SCR (€)'].median(),
                df_data['SCR (€)'].min(),
                df_data['SCR (€)'].max()
            ],
            'MCR (€)': [
                df_data['MCR (€)'].mean(),
                df_data['MCR (€)'].median(),
                df_data['MCR (€)'].min(),
                df_data['MCR (€)'].max()
            ],
            'Ratio de solvabilité (%)': [
                df_data['Ratio de solvabilité (%)'].mean(),
                df_data['Ratio de solvabilité (%)'].median(),
                df_data['Ratio de solvabilité (%)'].min(),
                df_data['Ratio de solvabilité (%)'].max()
            ]
        })
        
        df_data.to_excel(writer, sheet_name='Données', index=False)
        stats.to_excel(writer, sheet_name='Données', startrow=len(df_data) + 3, index=False)
        workbook = writer.book
        ws_graphs = workbook.create_sheet(title='Graphiques')
        
        for metric, start_row in [("SCR (€)", 1), ("MCR (€)", 15), ("Ratio de solvabilité (%)", 30)]:
            chart = openpyxl.chart.BarChart()
            chart.title = f"{metric} par société"
            chart.y_axis.title = metric
            chart.x_axis.title = "Société"
            
            data = openpyxl.chart.Reference(
                writer.sheets['Données'],
                min_col=df.columns.get_loc(metric) + 1,
                min_row=1,
                max_row=len(df_data) + 1,
                max_col=df.columns.get_loc(metric) + 1
            )
            cats = openpyxl.chart.Reference(
                writer.sheets['Données'],
                min_col=df.columns.get_loc('Société') + 1,
                min_row=2,
                max_row=len(df_data) + 1
            )
            
            chart.add_data(data, titles_from_data=True)
            chart.set_categories(cats)
            
            moyenne = df[df['Société'] == 'Moyenne'][metric].values[0]
            serie_moyenne = openpyxl.chart.ScatterChart()
            serie_moyenne.y_axis.crosses = "max"
            serie_moyenne.title = "Moyenne"
            
            ws_graphs.add_chart(chart, f"A{start_row}")
        
        for sheet in writer.sheets.values():
            for column in sheet.columns:
                max_length = 0
                column = [cell for cell in column]
                for cell in column:
                    try:
                        if len(str(cell.value)) > max_length:
                            max_length = len(str(cell.value))
                    except:
                        pass
                adjusted_width = (max_length + 2)
                sheet.column_dimensions[column[0].column_letter].width = adjusted_width

    buffer.seek(0)
    
    st.download_button(
        label="Télécharger les données",
        data=buffer,
        file_name=filename,
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

def create_matplotlib_figure(data, title, x_label, y_label, color='steelblue', moyenne=None):
    fig, ax = plt.subplots(figsize=(12, 8), dpi=120)
    
    # Créer le graphique en barres
    bars = ax.bar(data["Société"], data[y_label], color=color)
    
    # Utiliser la moyenne passée en paramètre
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
    
    # Configuration du graphique
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

def main():
    st.title("📊 Analyse de rapports SFCR")
    
    st.markdown("""
    ### Instructions
    - Chargez un ou plusieurs fichiers PDF
    - Pour un seul PDF : visualisation simple des données extraites
    - Pour plusieurs PDFs : comparaison automatique avec graphiques et statistiques
    - Possibilité de télécharger les données et graphiques au format XLSX
    """)
    
    st.sidebar.header("Import de fichiers")
    
    if st.sidebar.button("Effacer les données PDFs"):
        st.session_state.pdf_data = {}
        st.success("Les données PDFs ont été réinitialisées.")
    
    st.sidebar.subheader("Chargement de PDFs")
    uploaded_files = st.sidebar.file_uploader("Uploader vos fichiers .pdf", type="pdf", accept_multiple_files=True)
    
    if "pdf_data" not in st.session_state:
        st.session_state.pdf_data = {}
    
    prompt = PROMPT_TEMPLATE
    question = QUESTION_TEMPLATE
    
    if uploaded_files:
        progress_placeholder = st.empty()
        for pdf_file in uploaded_files:
            if pdf_file.name not in st.session_state.pdf_data:
                progress_placeholder.info(f"Traitement du fichier : {pdf_file.name}")
                with st.spinner(f"Traitement en cours..."):
                    source_id = add_pdf_from_file(pdf_file)
                    if source_id:
                        answer = chat_with_pdf(source_id, question, prompt=prompt)
                        if answer:
                            df_pdf = parse_solvency_text(answer)
                            st.session_state.pdf_data[pdf_file.name] = df_pdf
                            progress_placeholder.empty()
                        else:
                            progress_placeholder.error(f"Aucune réponse reçue pour {pdf_file.name}")
                    else:
                        progress_placeholder.error(f"Erreur lors de l'obtention du source_id pour {pdf_file.name}")
        
        if any(pdf_file.name not in st.session_state.pdf_data for pdf_file in uploaded_files):
            st.success("Traitement des fichiers terminé !")

    if st.session_state.pdf_data:
        nb_pdfs = len(st.session_state.pdf_data)
        
        if nb_pdfs == 1:
            pdf_name = list(st.session_state.pdf_data.keys())[0]
            df_selected = st.session_state.pdf_data[pdf_name]
            st.subheader(f"Données extraites pour : {pdf_name}")
            display_data(df_selected, show_full_analysis=False)
        else:
            st.subheader("Comparaison entre PDFs")
            selected_pdfs = st.sidebar.multiselect(
                "Sélectionnez les PDFs à comparer",
                list(st.session_state.pdf_data.keys()),
                default=list(st.session_state.pdf_data.keys())
            )
            
            if selected_pdfs:
                combined_df = pd.concat([st.session_state.pdf_data[name] for name in selected_pdfs], ignore_index=True)
                moyenne = pd.DataFrame({
                    'Société': ['Moyenne'],
                    'SCR (€)': [round(combined_df['SCR (€)'].mean(), 2)],
                    'MCR (€)': [round(combined_df['MCR (€)'].mean(), 2)],
                    'Ratio de solvabilité (%)': [round(combined_df['Ratio de solvabilité (%)'].mean(), 2)]
                })

                display_df = pd.concat([combined_df, moyenne], ignore_index=True)
                st.dataframe(display_df)
                download_excel(display_df, filename="metriques_comparaison.xlsx")
                tabs = st.tabs(["SCR ", "MCR ", "Ratio de solvabilité "])
                
                with tabs[0]:
                    fig_scr = create_matplotlib_figure(
                        combined_df,
                        "SCR par PDF", 
                        "Société", 
                        "SCR (€)", 
                        'skyblue',
                        moyenne=moyenne['SCR (€)'].values[0]
                    )
                    st.pyplot(fig_scr)
                
                with tabs[1]:
                    fig_mcr = create_matplotlib_figure(
                        combined_df,
                        "MCR par PDF", 
                        "Société", 
                        "MCR (€)", 
                        'lightgreen',
                        moyenne=moyenne['MCR (€)'].values[0]
                    )
                    st.pyplot(fig_mcr)
                
                with tabs[2]:
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
    else:
        st.warning("Aucun PDF n'a encore été traité. Veuillez uploader au moins un fichier .pdf.")

if __name__ == "__main__":
    main()
