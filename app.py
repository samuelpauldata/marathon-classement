import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
import pandas as pd
from datetime import date
import plotly.express as px

st.set_page_config(page_title="Classement Course", page_icon="🏃", layout="centered")

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

DISTANCES = ["5 km", "10 km", "Demi-marathon (21,1 km)", "Marathon (42,2 km)"]
DIST_KM = {"5 km": 5.0, "10 km": 10.0, "Demi-marathon (21,1 km)": 21.1, "Marathon (42,2 km)": 42.195}
AGE_GROUPS = ["18-34", "35-39", "40-44", "45-49", "50-54", "55-59", "60-64", "65-69", "70-74", "75-79", "80+"]
SEXES = ["Homme", "Femme"]
HEADERS = ["Nom", "Sexe", "Distance", "Categorie", "Evenement", "Date_PB", "Temps", "Secondes"]

@st.cache_resource
def get_sheet():
    creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=SCOPES)
    client = gspread.authorize(creds)
    sheet = client.open(st.secrets["sheet_name"]).sheet1
    if sheet.row_count == 0 or sheet.cell(1, 1).value != "Nom":
        sheet.clear()
        sheet.append_row(HEADERS)
    return sheet

def parse_time(time_str):
    parts = time_str.strip().split(":")
    try:
        if len(parts) == 3:
            h, m, s = int(parts[0]), int(parts[1]), int(parts[2])
        elif len(parts) == 2:
            h, m, s = 0, int(parts[0]), int(parts[1])
        else:
            return None
        if m >= 60 or s >= 60:
            return None
        return h * 3600 + m * 60 + s
    except ValueError:
        return None

def seconds_to_str(seconds):
    h = int(seconds) // 3600
    m = (int(seconds) % 3600) // 60
    s = int(seconds) % 60
    return f"{h}:{m:02d}:{s:02d}"

def pace_str(secondes, distance_label):
    km = DIST_KM.get(distance_label)
    if not km:
        return "—"
    pace_sec = secondes / km
    m = int(pace_sec) // 60
    s = int(pace_sec) % 60
    return f"{m}:{s:02d}/km"

def ecart_str(secondes, leader_sec):
    diff = int(secondes - leader_sec)
    if diff <= 0:
        return ""
    m = diff // 60
    s = diff % 60
    return f"+{m}:{s:02d}"

def load_data(sheet):
    records = sheet.get_all_records()
    if not records:
        return pd.DataFrame(columns=HEADERS)
    df = pd.DataFrame(records)
    if "Distance" not in df.columns:
        df["Distance"] = "Marathon (42,2 km)"
    if "Categorie" not in df.columns:
        df["Categorie"] = "—"
    if "Date_PB" not in df.columns:
        df["Date_PB"] = "—"
    if "Sexe" not in df.columns:
        df["Sexe"] = "Homme"
    if "Evenement" not in df.columns:
        df["Evenement"] = "—"
    df["Secondes"] = pd.to_numeric(df["Secondes"], errors="coerce")
    return df

def medal(rank):
    if rank == 1: return "🥇"
    if rank == 2: return "🥈"
    if rank == 3: return "🥉"
    return f"#{rank}"

def render_row(rank, row, leader_sec, show_category=False):
    bg = "#FFF9E6" if rank == 1 else "#F9F9F9" if rank % 2 == 0 else "#FFFFFF"
    cat_html = f'<span style="font-size:12px;color:#888;margin-left:6px;">({row["Categorie"]})</span>' if show_category and row.get("Categorie", "—") not in ("—", "") else ""
    date_html = f'<span style="font-size:12px;color:#aaa;margin-left:6px;">{row["Date_PB"]}</span>' if row.get("Date_PB", "—") not in ("—", "") else ""
    ev_html = f'<span style="font-size:12px;color:#6a9;margin-left:6px;">📍{row["Evenement"]}</span>' if row.get("Evenement", "—") not in ("—", "") else ""
    sexe_icon = "♂️" if row.get("Sexe") == "Homme" else "♀️"
    pace = pace_str(row["Secondes"], row["Distance"])
    ecart = ecart_str(row["Secondes"], leader_sec)
    ecart_html = f'<span style="font-size:13px;color:#e07000;margin-left:10px;">{ecart}</span>' if ecart else ""
    st.markdown(
        f"""
        <div style="display:flex;align-items:center;justify-content:space-between;
            padding:12px 20px;margin-bottom:6px;background:{bg};
            border-radius:10px;border:1px solid #EBEBEB;font-size:16px;">
            <span style="font-size:20px;min-width:50px;">{medal(rank)}</span>
            <span style="flex:1;font-weight:{'600' if rank <= 3 else '400'};">
                {sexe_icon} {row['Nom']}{cat_html}{ev_html}{date_html}
                <br><span style="font-size:12px;color:#999;">{pace}</span>
            </span>
            <span style="text-align:right;display:flex;align-items:center;">
                <span style="font-family:monospace;font-size:18px;color:#333;">{row['Temps']}</span>{ecart_html}
            </span>
        </div>
        """,
        unsafe_allow_html=True,
    )

# ── UI ───────────────────────────────────────────────────────────────────────
st.markdown("# 🏃 Classement Course")
st.markdown("Entrez les résultats de votre équipe et voyez le classement en temps réel.")

try:
    sheet = get_sheet()
    df = load_data(sheet)

    tab2, tab4, tab1, tab3 = st.tabs(["🏆 Classement", "📊 Graphique", "➕ Ajouter", "✏️ Modifier"])

    # ── TAB 1 : Ajouter ──────────────────────────────────────────────────────
    with tab1:
        st.subheader("Ajouter un coureur")
        col1, col2, col3 = st.columns([3, 1, 1])
        with col1:
            nom = st.text_input("Nom du coureur", placeholder="Ex: Marie Tremblay")
        with col2:
            sexe = st.selectbox("Sexe", SEXES)
        with col3:
            temps = st.text_input("Temps (H:MM:SS)", placeholder="Ex: 3:45:22")

        col4, col5, col6, col7 = st.columns([2, 1, 2, 1])
        with col4:
            distance = st.selectbox("Distance", DISTANCES, index=3)
        with col5:
            categorie = st.selectbox("Catégorie d'âge", AGE_GROUPS)
        with col6:
            evenement = st.text_input("Événement", placeholder="Ex: Buffalo, Toronto...")
        with col7:
            date_pb = st.date_input("Date du PB", value=date.today(), format="DD/MM/YYYY")

        if st.button("➕ Ajouter au classement", use_container_width=True):
            if not nom.strip():
                st.error("Entrez un nom.")
            elif not temps.strip():
                st.error("Entrez un temps.")
            else:
                secondes = parse_time(temps)
                if secondes is None:
                    st.error("Format invalide. Utilisez H:MM:SS (ex: 3:45:22).")
                else:
                    doublon = df[(df["Nom"].str.lower() == nom.strip().lower()) & (df["Distance"] == distance)]
                    if not doublon.empty:
                        st.warning(f"⚠️ **{nom}** est déjà dans le classement pour **{distance}**. Utilisez l'onglet Modifier.")
                    else:
                        sheet.append_row([nom.strip(), sexe, distance, categorie, evenement.strip() or "—", date_pb.strftime("%d/%m/%Y"), seconds_to_str(secondes), secondes])
                        st.success(f"✅ **{nom}** ajouté!")
                        st.cache_resource.clear()
                        st.rerun()

    # ── TAB 2 : Classement ───────────────────────────────────────────────────
    with tab2:
        if df.empty or len(df) == 0:
            st.info("Aucun coureur pour l'instant.")
        else:
            col_f1, col_f2, col_f3 = st.columns(3)
            with col_f1:
                distances_presentes = sorted(df["Distance"].unique().tolist(), key=lambda x: DISTANCES.index(x) if x in DISTANCES else 99)
                filtre_dist = st.radio("Distance", ["Toutes"] + distances_presentes, horizontal=True)
            with col_f2:
                cats_presentes = [g for g in AGE_GROUPS if g in df["Categorie"].unique()]
                filtre_cat = st.radio("Catégorie d'âge", ["Toutes"] + cats_presentes, horizontal=True)
            with col_f3:
                filtre_sexe = st.radio("Sexe", ["Tous", "Homme", "Femme"], horizontal=True)

            evenements_presents = sorted([e for e in df["Evenement"].unique() if e not in ("—", "")])
            if evenements_presents:
                filtre_ev = st.radio("Événement", ["Tous"] + evenements_presents, horizontal=True)
            else:
                filtre_ev = "Tous"

            tri = st.radio("Trier par", ["🏆 Temps", "📅 Date du PB (récent → ancien)", "📅 Date du PB (ancien → récent)"], horizontal=True)

            df_filtre = df.copy()
            if filtre_dist != "Toutes":
                df_filtre = df_filtre[df_filtre["Distance"] == filtre_dist]
            if filtre_cat != "Toutes":
                df_filtre = df_filtre[df_filtre["Categorie"] == filtre_cat]
            if filtre_sexe != "Tous":
                df_filtre = df_filtre[df_filtre["Sexe"] == filtre_sexe]
            if filtre_ev != "Tous":
                df_filtre = df_filtre[df_filtre["Evenement"] == filtre_ev]

            if tri == "🏆 Temps":
                df_sorted = df_filtre.dropna(subset=["Secondes"]).sort_values("Secondes").reset_index(drop=True)
            else:
                def parse_date(d):
                    try:
                        return pd.to_datetime(d, format="%d/%m/%Y")
                    except:
                        return pd.NaT
                df_filtre = df_filtre.copy()
                df_filtre["Date_parsed"] = df_filtre["Date_PB"].apply(parse_date)
                ascending = (tri == "📅 Date du PB (ancien → récent)")
                df_sorted = df_filtre.sort_values("Date_parsed", ascending=ascending).reset_index(drop=True)

            show_category = (filtre_cat == "Toutes")

            if df_sorted.empty:
                st.info("Aucun coureur pour ces filtres.")
            else:
                c1, c2, c3 = st.columns(3)
                c1.metric("Coureurs", len(df_sorted))
                c2.metric("Meilleur temps", df_sorted.iloc[0]["Temps"])
                c3.metric("Temps moyen", seconds_to_str(int(df_sorted["Secondes"].mean())))
                st.markdown("")

                if filtre_dist == "Toutes":
                    for dist in distances_presentes:
                        df_dist = df_sorted[df_sorted["Distance"] == dist].reset_index(drop=True)
                        if df_dist.empty:
                            continue
                        st.markdown(f"#### {dist}")
                        leader_sec = df_dist.iloc[0]["Secondes"]
                        for i, row in df_dist.iterrows():
                            render_row(i + 1, row, leader_sec, show_category=show_category)
                else:
                    leader_sec = df_sorted.iloc[0]["Secondes"]
                    for i, row in df_sorted.iterrows():
                        render_row(i + 1, row, leader_sec, show_category=show_category)

            st.markdown("---")
            with st.expander("🗑️ Supprimer un coureur"):
                df_display = df.copy()
                df_display["Label"] = df_display["Nom"] + " — " + df_display["Distance"]
                labels = df_display["Label"].tolist()
                label_suppr = st.selectbox("Choisir le coureur à supprimer", labels)
                if st.button("Supprimer", type="secondary"):
                    idx = labels.index(label_suppr)
                    nom_suppr = df_display.iloc[idx]["Nom"]
                    dist_suppr = df_display.iloc[idx]["Distance"]
                    all_values = sheet.get_all_values()
                    for i, row in enumerate(all_values):
                        if len(row) >= 2 and row[0] == nom_suppr and row[1] == dist_suppr:
                            sheet.delete_rows(i + 1)
                            st.success(f"**{nom_suppr}** ({dist_suppr}) supprimé.")
                            st.cache_resource.clear()
                            st.rerun()
                            break

    # ── TAB 3 : Modifier ─────────────────────────────────────────────────────
    with tab3:
        st.subheader("Modifier un résultat")
        if df.empty or len(df) == 0:
            st.info("Aucun coureur à modifier.")
        else:
            df_display = df.copy()
            df_display["Label"] = df_display["Nom"] + " — " + df_display["Distance"]
            labels = df_display["Label"].tolist()
            label_modif = st.selectbox("Choisir le coureur à modifier", labels)
            idx = labels.index(label_modif)
            row_data = df_display.iloc[idx]

            col1, col2, col3 = st.columns([2, 1, 1])
            with col1:
                nouveau_temps = st.text_input("Nouveau temps (H:MM:SS)", value=row_data["Temps"])
            with col2:
                nouveau_sexe = st.selectbox("Sexe", SEXES, index=SEXES.index(row_data["Sexe"]) if row_data["Sexe"] in SEXES else 0, key="modif_sexe")
            with col3:
                try:
                    date_actuelle = pd.to_datetime(row_data["Date_PB"], format="%d/%m/%Y").date()
                except:
                    date_actuelle = date.today()
                nouvelle_date = st.date_input("Date du PB", value=date_actuelle, format="DD/MM/YYYY")

            col4, col5 = st.columns(2)
            with col4:
                nouvelle_cat = st.selectbox("Catégorie d'âge", AGE_GROUPS,
                    index=AGE_GROUPS.index(row_data["Categorie"]) if row_data["Categorie"] in AGE_GROUPS else 0,
                    key="modif_cat")
            with col5:
                nouvel_ev = st.text_input("Événement", value=row_data["Evenement"] if row_data["Evenement"] != "—" else "", key="modif_ev")

            if st.button("💾 Sauvegarder les modifications", use_container_width=True):
                secondes = parse_time(nouveau_temps)
                if secondes is None:
                    st.error("Format invalide. Utilisez H:MM:SS.")
                else:
                    all_values = sheet.get_all_values()
                    for i, row in enumerate(all_values):
                        if len(row) >= 2 and row[0] == row_data["Nom"] and row[1] == row_data["Distance"]:
                            sheet.update(f"A{i+1}:H{i+1}", [[
                                row_data["Nom"], nouveau_sexe, row_data["Distance"],
                                nouvelle_cat, nouvel_ev.strip() or "—",
                                nouvelle_date.strftime("%d/%m/%Y"),
                                seconds_to_str(secondes), secondes
                            ]])
                            st.success(f"✅ **{row_data['Nom']}** mis à jour!")
                            st.cache_resource.clear()
                            st.rerun()
                            break

    # ── TAB 4 : Graphique ────────────────────────────────────────────────────
    with tab4:
        st.subheader("Graphique des temps")
        if df.empty or len(df) == 0:
            st.info("Aucune donnée à afficher.")
        else:
            distances_presentes = sorted(df["Distance"].unique().tolist(), key=lambda x: DISTANCES.index(x) if x in DISTANCES else 99)
            col_g1, col_g2 = st.columns(2)
            with col_g1:
                dist_graph = st.selectbox("Distance", distances_presentes, key="graph_dist")
            with col_g2:
                couleur_par = st.radio("Couleur par", ["Catégorie d'âge", "Sexe", "Événement"], horizontal=True)

            couleur_col = {"Catégorie d'âge": "Categorie", "Sexe": "Sexe", "Événement": "Evenement"}[couleur_par]

            df_graph = df[df["Distance"] == dist_graph].dropna(subset=["Secondes"]).sort_values("Secondes").reset_index(drop=True)
            if df_graph.empty:
                st.info(f"Aucun coureur pour {dist_graph}.")
            else:
                df_graph = df_graph.copy()
                df_graph["Pace"] = df_graph.apply(lambda r: pace_str(r["Secondes"], r["Distance"]), axis=1)
                df_graph["Minutes"] = df_graph["Secondes"] / 60
                leader_sec = df_graph.iloc[0]["Secondes"]
                df_graph["Écart leader"] = df_graph["Secondes"].apply(lambda s: ecart_str(s, leader_sec) or "—")

                # Tick labels Y en H:MM:SS
                y_min = df_graph["Minutes"].min()
                y_max = df_graph["Minutes"].max()
                padding = max((y_max - y_min) * 0.15, 2)
                tick_count = 8
                tick_step = (y_max - y_min + padding * 2) / tick_count
                tick_vals = [y_min - padding + i * tick_step for i in range(tick_count + 1)]
                tick_texts = [seconds_to_str(int(v * 60)) for v in tick_vals]

                # Moyenne
                moyenne_min = df_graph["Minutes"].mean()
                moyenne_str = seconds_to_str(int(moyenne_min * 60))

                import plotly.graph_objects as go
                fig = go.Figure()

                # Ligne de connexion
                fig.add_trace(go.Scatter(
                    x=df_graph["Nom"], y=df_graph["Minutes"],
                    mode="lines",
                    line=dict(color="#4A90D9", width=2, dash="solid"),
                    showlegend=False,
                    hoverinfo="skip"
                ))

                # Points colorés
                fig.add_trace(go.Scatter(
                    x=df_graph["Nom"], y=df_graph["Minutes"],
                    mode="markers+text",
                    text=df_graph["Temps"],
                    textposition="top center",
                    textfont=dict(size=11),
                    marker=dict(size=12, color="#FC4C02", line=dict(color="white", width=2)),
                    customdata=df_graph[["Pace", "Écart leader", "Evenement", "Date_PB", "Categorie", "Sexe"]].values,
                    hovertemplate=(
                        "<b>%{x}</b><br>"
                        "⏱ Temps : %{text}<br>"
                        "🏃 Pace : %{customdata[0]}<br>"
                        "📊 Écart leader : %{customdata[1]}<br>"
                        "📍 Événement : %{customdata[2]}<br>"
                        "📅 Date PB : %{customdata[3]}<br>"
                        "👤 Catégorie : %{customdata[4]} · %{customdata[5]}<extra></extra>"
                    ),
                    name="Coureurs"
                ))

                # Ligne moyenne
                fig.add_hline(
                    y=moyenne_min,
                    line_dash="dot",
                    line_color="#888",
                    line_width=1.5,
                    annotation_text=f"Moyenne équipe : {moyenne_str}",
                    annotation_position="top right",
                    annotation_font_color="#888"
                )

                fig.update_layout(
                    title=f"Temps — {dist_graph}",
                    plot_bgcolor="#FAFAFA",
                    paper_bgcolor="white",
                    height=500,
                    yaxis=dict(
                        tickvals=tick_vals,
                        ticktext=tick_texts,
                        range=[y_min - padding, y_max + padding],
                        title="Temps",
                        gridcolor="#EBEBEB"
                    ),
                    xaxis=dict(title="", gridcolor="#EBEBEB"),
                    showlegend=False,
                    margin=dict(t=60, b=60)
                )
                st.plotly_chart(fig, use_container_width=True)

except Exception as e:
    st.error(f"Erreur de connexion: {e}")
    st.info("Vérifiez que vos secrets Streamlit (gcp_service_account et sheet_name) sont bien configurés.")
