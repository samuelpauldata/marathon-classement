import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
import pandas as pd
from datetime import date

# ── Config ──────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Classement Course",
    page_icon="🏃",
    layout="centered"
)

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

DISTANCES = ["5 km", "10 km", "Demi-marathon (21,1 km)", "Marathon (42,2 km)"]
AGE_GROUPS = ["18-34", "35-39", "40-44", "45-49", "50-54", "55-59", "60-64", "65-69", "70-74", "75-79", "80+"]

# ── Google Sheets connection ─────────────────────────────────────────────────
@st.cache_resource
def get_sheet():
    creds = Credentials.from_service_account_info(
        st.secrets["gcp_service_account"],
        scopes=SCOPES,
    )
    client = gspread.authorize(creds)
    sheet = client.open(st.secrets["sheet_name"]).sheet1
    if sheet.row_count == 0 or sheet.cell(1, 1).value != "Nom":
        sheet.clear()
        sheet.append_row(["Nom", "Distance", "Categorie", "Date_PB", "Temps", "Secondes"])
    return sheet

def parse_time(time_str):
    time_str = time_str.strip()
    parts = time_str.split(":")
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

def load_data(sheet):
    records = sheet.get_all_records()
    if not records:
        return pd.DataFrame(columns=["Nom", "Distance", "Categorie", "Date_PB", "Temps", "Secondes"])
    df = pd.DataFrame(records)
    if "Distance" not in df.columns:
        df["Distance"] = "Marathon (42,2 km)"
    if "Categorie" not in df.columns:
        df["Categorie"] = "—"
    if "Date_PB" not in df.columns:
        df["Date_PB"] = "—"
    df["Secondes"] = pd.to_numeric(df["Secondes"], errors="coerce")
    return df

def medal(rank):
    if rank == 1: return "🥇"
    if rank == 2: return "🥈"
    if rank == 3: return "🥉"
    return f"#{rank}"

def render_row(rank, row, show_category=False):
    bg = "#FFF9E6" if rank == 1 else "#F9F9F9" if rank % 2 == 0 else "#FFFFFF"
    cat_html = f'<span style="font-size:12px; color:#888; margin-left:8px;">({row["Categorie"]})</span>' if show_category and row.get("Categorie", "—") != "—" else ""
    date_html = f'<span style="font-size:12px; color:#aaa; margin-left:8px;">{row["Date_PB"]}</span>' if row.get("Date_PB", "—") != "—" else ""
    st.markdown(
        f"""
        <div style="
            display: flex;
            align-items: center;
            justify-content: space-between;
            padding: 12px 20px;
            margin-bottom: 6px;
            background: {bg};
            border-radius: 10px;
            border: 1px solid #EBEBEB;
            font-size: 16px;
        ">
            <span style="font-size: 20px; min-width: 50px;">{medal(rank)}</span>
            <span style="flex: 1; font-weight: {'600' if rank <= 3 else '400'};">
                {row['Nom']}{cat_html}{date_html}
            </span>
            <span style="font-family: monospace; font-size: 18px; color: #333;">{row['Temps']}</span>
        </div>
        """,
        unsafe_allow_html=True,
    )

# ── UI ───────────────────────────────────────────────────────────────────────
st.markdown("# 🏃 Classement Course")
st.markdown("Entrez les résultats de votre équipe et voyez le classement en temps réel.")

try:
    sheet = get_sheet()

    # ── Ajouter un coureur ────────────────────────────────────────────────────
    st.markdown("---")
    st.subheader("Ajouter un coureur")

    col1, col2 = st.columns([2, 1])
    with col1:
        nom = st.text_input("Nom du coureur", placeholder="Ex: Marie Tremblay")
    with col2:
        temps = st.text_input("Temps (H:MM:SS)", placeholder="Ex: 3:45:22")

    col3, col4, col5 = st.columns([2, 1, 1])
    with col3:
        distance = st.selectbox("Distance", DISTANCES, index=3)
    with col4:
        categorie = st.selectbox("Catégorie d'âge", AGE_GROUPS)
    with col5:
        date_pb = st.date_input("Date du PB", value=date.today(), format="DD/MM/YYYY")

    if st.button("➕ Ajouter au classement", use_container_width=True):
        if not nom.strip():
            st.error("Entrez un nom.")
        elif not temps.strip():
            st.error("Entrez un temps.")
        else:
            secondes = parse_time(temps)
            if secondes is None:
                st.error("Format invalide. Utilisez H:MM:SS (ex: 3:45:22) ou MM:SS.")
            else:
                df = load_data(sheet)
                doublon = df[(df["Nom"].str.lower() == nom.strip().lower()) & (df["Distance"] == distance)]
                if not doublon.empty:
                    st.warning(f"⚠️ **{nom}** est déjà dans le classement pour **{distance}**.")
                else:
                    sheet.append_row([nom.strip(), distance, categorie, date_pb.strftime("%d/%m/%Y"), seconds_to_str(secondes), secondes])
                    st.success(f"✅ **{nom}** ajouté!")
                    st.cache_resource.clear()
                    st.rerun()

    # ── Classement ────────────────────────────────────────────────────────────
    st.markdown("---")
    st.subheader("Classement")

    df = load_data(sheet)

    if df.empty or len(df) == 0:
        st.info("Aucun coureur pour l'instant. Ajoutez le premier résultat ci-dessus!")
    else:
        # Filtres
        col_f1, col_f2 = st.columns(2)
        with col_f1:
            distances_presentes = sorted(df["Distance"].unique().tolist(), key=lambda x: DISTANCES.index(x) if x in DISTANCES else 99)
            filtre_dist = st.radio("Distance", ["Toutes"] + distances_presentes, horizontal=True)
        with col_f2:
            cats_presentes = [g for g in AGE_GROUPS if g in df["Categorie"].unique()]
            filtre_cat = st.radio("Catégorie d'âge", ["Toutes"] + cats_presentes, horizontal=True)

        col_f3, col_f4 = st.columns([1, 1])
        with col_f3:
            tri = st.radio("Trier par", ["🏆 Temps", "📅 Date du PB (récent → ancien)", "📅 Date du PB (ancien → récent)"], horizontal=False)

        # Appliquer filtres
        df_filtre = df.copy()
        if filtre_dist != "Toutes":
            df_filtre = df_filtre[df_filtre["Distance"] == filtre_dist]
        if filtre_cat != "Toutes":
            df_filtre = df_filtre[df_filtre["Categorie"] == filtre_cat]

        # Appliquer tri
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

            # Grouper par distance si "Toutes"
            if filtre_dist == "Toutes":
                for dist in distances_presentes:
                    df_dist = df_sorted[df_sorted["Distance"] == dist].reset_index(drop=True)
                    if df_dist.empty:
                        continue
                    st.markdown(f"#### {dist}")
                    for i, row in df_dist.iterrows():
                        render_row(i + 1, row, show_category=show_category)
            else:
                for i, row in df_sorted.iterrows():
                    render_row(i + 1, row, show_category=show_category)

    # ── Supprimer un coureur ─────────────────────────────────────────────────
    if not df.empty and len(df) > 0:
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

except Exception as e:
    st.error(f"Erreur de connexion: {e}")
    st.info("Vérifiez que vos secrets Streamlit (gcp_service_account et sheet_name) sont bien configurés.")
