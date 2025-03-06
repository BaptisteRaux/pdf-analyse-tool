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

API_KEY = "sec_DfgTFrXbeytiqyKpk3uqhR3QIUlr1qGH"

PROMPT_TEMPLATE = """
Donne les réponses sous cette forme SCR : X, MCR : X, EOF : X, Ratio de solvabilité : X, 
Le SCR, MCR et EOF sont des montants en euros. 
Pour l'EOF (fonds propres éligibles), cherche dans le document les termes comme "fonds propres éligibles", "fonds propres disponibles" ou "fonds propres Solvabilité II".
IMPORTANT : Si tu trouves une valeur en millions d'euros, tu dois la convertir en multipliant par 1 000 000.
Par exemple :
- Si tu trouves "10 642 millions d'euros", tu dois écrire "10 642 000 000€"
- Si tu trouves "1,5 milliards d'euros", tu dois écrire "1 500 000 000€"
Ne laisse aucune lettre pour désigner les millions ou milliards, uniquement le nombre complet en euros.
"""

QUESTION_TEMPLATE = """
0) Nom de la société : 
1) Donne le SCR 
2) Donne le MCR 
3) Donne les fonds propres éligibles (EOF). Cherche dans le document les mentions de "fonds propres éligibles", "fonds propres disponibles" ou "fonds propres Solvabilité II. ATTENTION : Si la valeur est en millions d'euros, multiplie par 1 000 000 pour donner le montant en euros.
4) Donne le ratio de solvabilité, également appelé le taux de couverture
"""

def parse_solvency_text(text):
    patterns = {
        'company': r"0\)\s*Nom de la société\s*:\s*(.+)",
        'scr': r"1\)\s*SCR\s*:\s*([\d\s]+)€",
        'mcr': r"2\)\s*MCR\s*:\s*([\d\s]+)€",
        'eof': r"3\)\s*(?:(?:Fonds\s+propres\s+éligibles\s*(?:\(EOF\))?|EOF)\s*:\s*([\d\s]+)€)",
        'ratio': r"4\)\s*Ratio de solvabilité\s*:\s*([\d,\.]+)\s*%"
    }
    data = []
    current_entry = {
        'Société': None, 
        'SCR (€)': np.nan, 
        'MCR (€)': np.nan, 
        'Fonds propres (€)': np.nan,
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
                        'Fonds propres (€)': np.nan,
                        'Ratio de solvabilité (%)': np.nan
                    }
                elif key == 'scr':
                    current_entry['SCR (€)'] = int(match.group(1).replace(" ", ""))
                elif key == 'mcr':
                    current_entry['MCR (€)'] = int(match.group(1).replace(" ", ""))
                elif key == 'eof':
                    value = match.group(1) if match.group(1) else match.group(2)
                    value = int(value.replace(" ", ""))
                    if "million" in line:
                        value = value * 1_000_000
                    current_entry['Fonds propres (€)'] = value
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


def download_excel(df, filename="analyse_sfcr.xlsx"):
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
            'Fonds propres (€)': [
                df_data['Fonds propres (€)'].mean(),
                df_data['Fonds propres (€)'].median(),
                df_data['Fonds propres (€)'].min(),
                df_data['Fonds propres (€)'].max()
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
        ws = writer.sheets['Données']
        header_style = openpyxl.styles.NamedStyle(
            name='header',
            font=openpyxl.styles.Font(bold=True, color='FFFFFF'),
            fill=openpyxl.styles.PatternFill(start_color='366092', end_color='366092', fill_type='solid'),
            alignment=openpyxl.styles.Alignment(horizontal='center', vertical='center'),
            border=openpyxl.styles.Border(
                left=openpyxl.styles.Side(style='thin'),
                right=openpyxl.styles.Side(style='thin'),
                top=openpyxl.styles.Side(style='thin'),
                bottom=openpyxl.styles.Side(style='thin')
            )
        )

        for cell in ws[1]:
            cell.style = header_style

        stats_header_row = len(df_data) + 4
        for cell in ws[stats_header_row]:
            cell.style = header_style

        for column in ws.columns:
            max_length = 0
            column = [cell for cell in column]
            for cell in column:
                try:
                    if len(str(cell.value)) > max_length:
                        max_length = len(str(cell.value))
                except:
                    pass
            adjusted_width = (max_length + 2)
            ws.column_dimensions[column[0].column_letter].width = adjusted_width

        ws.freeze_panes = 'A2'
        ws_graphs = workbook.create_sheet(title='Graphiques')
        for metric, start_row in [
            ("SCR (€)", 1), 
            ("MCR (€)", 15), 
            ("Fonds propres (€)", 30),
            ("Ratio de solvabilité (%)", 45)
        ]:
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
            serie_moyenne = openpyxl.chart.ScatterChart()
            serie_moyenne.y_axis.crosses = "max"
            serie_moyenne.title = "Moyenne"
            ws_graphs.add_chart(chart, f"A{start_row}")
        
        for column in ws_graphs.columns:
            max_length = 0
            column = [cell for cell in column]
            for cell in column:
                try:
                    if len(str(cell.value)) > max_length:
                        max_length = len(str(cell.value))
                except:
                    pass

            adjusted_width = (max_length + 2)
            ws_graphs.column_dimensions[column[0].column_letter].width = adjusted_width

    buffer.seek(0)
    st.download_button(
        label="Télécharger les données",
        data=buffer,
        file_name=filename,
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

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
                    combined_df = pd.concat([st.session_state.pdf_data[name] for name in selected_pdfs], ignore_index=True)
                    moyenne = pd.DataFrame({
                        'Société': ['Moyenne'],
                        'SCR (€)': [round(combined_df['SCR (€)'].mean(), 2)],
                        'MCR (€)': [round(combined_df['MCR (€)'].mean(), 2)],
                        'Fonds propres (€)': [round(combined_df['Fonds propres (€)'].mean(), 2)],
                        'Ratio de solvabilité (%)': [round(combined_df['Ratio de solvabilité (%)'].mean(), 2)]
                    })

                    display_df = pd.concat([combined_df, moyenne], ignore_index=True)
                    
                    download_excel(display_df, filename="analyse_sfcr.xlsx")
                    st.subheader("Comparaison entre PDFs")
                    st.dataframe(display_df)
                    
                    metric_tabs = st.tabs(["SCR ", "MCR ", "Fonds propres ", "Ratio de solvabilité "])
                    
                    with metric_tabs[0]:
                        fig_scr = create_matplotlib_figure(
                            combined_df,
                            "SCR par PDF", 
                            "Société", 
                            "SCR (€)", 
                            'skyblue',
                            moyenne=moyenne['SCR (€)'].values[0]
                        )
                        st.pyplot(fig_scr)
                    
                    with metric_tabs[1]:
                        fig_mcr = create_matplotlib_figure(
                            combined_df,
                            "MCR par PDF", 
                            "Société", 
                            "MCR (€)", 
                            'lightgreen',
                            moyenne=moyenne['MCR (€)'].values[0]
                        )
                        st.pyplot(fig_mcr)
                    
                    with metric_tabs[2]:
                        fig_eof = create_matplotlib_figure(
                            combined_df,
                            "Fonds propres par PDF",
                            "Société", 
                            "Fonds propres (€)",
                            'orange',
                            moyenne=moyenne['Fonds propres (€)'].values[0]
                        )
                        st.pyplot(fig_eof)
                    
                    with metric_tabs[3]:
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