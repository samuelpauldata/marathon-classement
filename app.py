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
    df = df[df["Secondes"] > 0].dropna(subset=["Secondes", "Nom"])
    df = df[df["Nom"].astype(str).str.strip() != ""]
    return df

def medal(rank):
    if rank == 1: return "1"
    if rank == 2: return "2"
    if rank == 3: return "3"
    return f"#{rank}"

# Lucide SVG icons (flat, stroke-based)
ICON_MAP = {
    "pin":      "📍",
    "calendar": "📅",
    "user_m":   "♂",
    "user_f":   "♀",
    "zap":      "⚡",
}

def esc(val):
    """Escape HTML special characters from user data."""
    return str(val).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")

def rank_badge(rank):
    if rank == 1:
        color, bg = "#FC4C02", "#fff0eb"
    elif rank == 2:
        color, bg = "#6B7280", "#F3F4F6"
    elif rank == 3:
        color, bg = "#B45309", "#FEF3C7"
    else:
        return f'<span style="font-size:11px;color:#ccc;font-weight:700;min-width:28px;text-align:center;">#{rank}</span>'
    return f'<span style="display:inline-flex;align-items:center;justify-content:center;width:26px;height:26px;border-radius:50%;background:{bg};color:{color};font-size:12px;font-weight:800;">{rank}</span>'

def render_row(rank, row, leader_sec, show_category=False):
    is_leader = rank == 1
    shadow = "0 2px 12px rgba(252,76,2,0.10)" if is_leader else "0 1px 4px rgba(0,0,0,0.06)"
    border_left = "3px solid #FC4C02" if is_leader else "3px solid transparent"
    time_color = "#FC4C02" if is_leader else "#1a1a1a"

    nom_safe = esc(row['Nom'])
    cat_safe = esc(row.get("Categorie", "—"))
    date_safe = esc(row.get("Date_PB", "—"))
    ev_safe = esc(row.get("Evenement", "—"))
    temps_safe = esc(row['Temps'])
    pace_safe = esc(pace_str(row["Secondes"], row["Distance"]))

    cat_html = f'<span style="font-size:10px;color:#bbb;margin-left:5px;font-weight:500;text-transform:uppercase;letter-spacing:0.4px;">{cat_safe}</span>' if show_category and cat_safe not in ("—", "") else ""
    date_html = f'<span style="font-size:10px;color:#ccc;margin-left:6px;">{ICON_MAP["calendar"]} {date_safe}</span>' if date_safe not in ("—", "") else ""
    ev_html = f'<span style="font-size:10px;color:#FC4C02;font-weight:600;margin-left:6px;">{ICON_MAP["pin"]} {ev_safe}</span>' if ev_safe not in ("—", "") else ""
    sexe_icon = f'<span style="font-size:10px;color:#aaa;">{ICON_MAP["user_m"]}</span>' if row.get("Sexe") == "Homme" else f'<span style="font-size:10px;color:#FC4C02;">{ICON_MAP["user_f"]}</span>'

    ecart = ecart_str(row["Secondes"], leader_sec)
    ecart_html = f'<span style="font-size:11px;color:#bbb;margin-left:8px;font-weight:500;">{esc(ecart)}</span>' if ecart else ""

    st.markdown(
        f"""
        <div style="display:flex;align-items:center;justify-content:space-between;
            padding:13px 16px;margin-bottom:6px;background:white;
            border-radius:12px;box-shadow:{shadow};border-left:{border_left};">
            <span style="min-width:36px;text-align:center;">{rank_badge(rank)}</span>
            <span style="flex:1;padding-left:12px;">
                <div style="display:flex;align-items:center;gap:5px;flex-wrap:wrap;line-height:1.4;">
                    {sexe_icon}
                    <span style="font-size:14px;font-weight:{'700' if rank <= 3 else '600'};color:#1a1a1a;">{nom_safe}</span>
                    {cat_html}{ev_html}{date_html}
                </div>
                <div style="margin-top:3px;">
                    <span style="font-size:11px;color:#ccc;letter-spacing:0.2px;">{ICON_MAP["zap"]} {pace_safe}</span>
                </div>
            </span>
            <span style="display:flex;align-items:center;">
                <span style="font-family:monospace;font-size:16px;font-weight:700;color:{time_color};">{temps_safe}</span>{ecart_html}
            </span>
        </div>
        """,
        unsafe_allow_html=True,
    )

# ── UI ───────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

    html, body, [class*="css"] { font-family: 'Inter', sans-serif; }

    /* Hide Streamlit header */
    header[data-testid="stHeader"] { display: none !important; }
    .stApp { background-color: #F5F5F5; }
    .block-container { padding-top: 1.5rem !important; }

    /* Header */
    .main-title {
        font-size: 2.2rem; font-weight: 800; color: #1a1a1a;
        letter-spacing: -1px; margin-bottom: 4px; line-height: 1.1;
    }
    .main-title span { color: #FC4C02; }
    .main-subtitle { font-size: 0.85rem; color: #aaa; margin-bottom: 1.5rem; letter-spacing: 0.3px; }

    /* Tabs */
    .stTabs [data-baseweb="tab-list"] {
        gap: 0; background: white; border-radius: 12px;
        padding: 4px; box-shadow: 0 1px 4px rgba(0,0,0,0.08); border: none;
    }
    .stTabs [data-baseweb="tab"] {
        font-size: 0.82rem; font-weight: 600; color: #999;
        padding: 8px 18px; border-radius: 8px; border: none !important;
    }
    .stTabs [aria-selected="true"] {
        background: #FC4C02 !important; color: white !important;
        box-shadow: 0 2px 8px rgba(252,76,2,0.3);
    }
    .stTabs [data-baseweb="tab-border"] { display: none; }

    /* Metrics — card style */
    [data-testid="metric-container"] {
        background: white; border-radius: 12px;
        padding: 16px 20px !important;
        box-shadow: 0 1px 4px rgba(0,0,0,0.07);
        border-left: 4px solid #FC4C02;
    }
    [data-testid="stMetricValue"] { font-size: 1.5rem !important; font-weight: 800 !important; color: #1a1a1a !important; }
    [data-testid="stMetricLabel"] { font-size: 0.72rem !important; color: #aaa !important; text-transform: uppercase; letter-spacing: 0.8px; font-weight: 600; }

    /* Buttons */
    .stButton > button {
        background: #FC4C02 !important; color: white !important;
        border: none !important; border-radius: 10px !important;
        font-weight: 700 !important; font-size: 0.9rem !important;
        padding: 12px 24px !important; letter-spacing: 0.3px !important;
        box-shadow: 0 4px 12px rgba(252,76,2,0.3) !important;
        transition: all 0.2s !important;
    }
    .stButton > button:hover {
        background: #e04400 !important;
        box-shadow: 0 6px 16px rgba(252,76,2,0.4) !important;
        transform: translateY(-1px) !important;
    }

    /* Section titles */
    h3 { color: #1a1a1a !important; font-weight: 700 !important; font-size: 1.05rem !important; letter-spacing: -0.3px; }
    h4 {
        color: #FC4C02 !important; font-size: 0.78rem !important; font-weight: 700 !important;
        text-transform: uppercase; letter-spacing: 1px; margin-top: 1.5rem !important;
        padding-bottom: 6px; border-bottom: 1px solid #f0f0f0;
    }

    /* Inputs */
    .stTextInput input {
        border-radius: 8px !important; border: 1.5px solid #e8e8e8 !important;
        background: white !important; font-size: 0.9rem !important;
        box-shadow: 0 1px 3px rgba(0,0,0,0.04) !important;
    }
    .stTextInput input:focus {
        border-color: #FC4C02 !important;
        box-shadow: 0 0 0 3px rgba(252,76,2,0.1) !important;
    }

    /* Radio */
    .stRadio label { font-size: 0.82rem !important; color: #666 !important; font-weight: 500; }

    /* Expander */
    .streamlit-expanderHeader { font-size: 0.85rem !important; color: #999 !important; }

    /* Divider */
    hr { border-color: #ebebeb !important; margin: 1.2rem 0 !important; }

    /* Form sections */
    .stSelectbox label, .stTextInput label, .stDateInput label {
        font-size: 0.78rem !important; font-weight: 600 !important;
        color: #888 !important; text-transform: uppercase; letter-spacing: 0.5px;
    }
</style>
""", unsafe_allow_html=True)

st.markdown('<div class="main-title">🏃 Classement <span>Course</span></div>', unsafe_allow_html=True)
st.markdown('<div class="main-subtitle">Résultats et classement de votre équipe en temps réel</div>', unsafe_allow_html=True)

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

                # Points colorés par groupe
                groupes = df_graph[couleur_col].unique()
                colors = px.colors.qualitative.Set2
                for i, groupe in enumerate(groupes):
                    df_g = df_graph[df_graph[couleur_col] == groupe]
                    fig.add_trace(go.Scatter(
                        x=df_g["Nom"], y=df_g["Minutes"],
                        mode="markers+text",
                        name=str(groupe),
                        text=df_g["Temps"],
                        textposition="top center",
                        textfont=dict(size=11),
                        marker=dict(size=12, color=colors[i % len(colors)], line=dict(color="white", width=2)),
                        customdata=df_g[["Pace", "Écart leader", "Evenement", "Date_PB", "Categorie", "Sexe"]].values,
                        hovertemplate=(
                            "<b>%{x}</b><br>"
                            "⏱ Temps : %{text}<br>"
                            "🏃 Pace : %{customdata[0]}<br>"
                            "📊 Écart leader : %{customdata[1]}<br>"
                            "📍 Événement : %{customdata[2]}<br>"
                            "📅 Date PB : %{customdata[3]}<br>"
                            "👤 Catégorie : %{customdata[4]} · %{customdata[5]}<extra></extra>"
                        ),
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
                        range=[y_max + padding, y_min - padding],
                        title="Temps",
                        gridcolor="#EBEBEB"
                    ),
                    xaxis=dict(title="", gridcolor="#EBEBEB"),
                    showlegend=True,
                    margin=dict(t=60, b=60)
                )
                st.plotly_chart(fig, use_container_width=True)

except Exception as e:
    st.error(f"Erreur de connexion: {e}")
    st.info("Vérifiez que vos secrets Streamlit (gcp_service_account et sheet_name) sont bien configurés.")
