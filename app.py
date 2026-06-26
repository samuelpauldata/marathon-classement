import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
import pandas as pd
import re

# ── Config ──────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Classement Marathon",
    page_icon="🏃",
    layout="centered"
)

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

# ── Google Sheets connection ─────────────────────────────────────────────────
@st.cache_resource
def get_sheet():
    creds = Credentials.from_service_account_info(
        st.secrets["gcp_service_account"],
        scopes=SCOPES,
    )
    client = gspread.authorize(creds)
    sheet = client.open(st.secrets["sheet_name"]).sheet1
    # Create headers if sheet is empty
    if sheet.row_count == 0 or sheet.cell(1, 1).value != "Nom":
        sheet.clear()
        sheet.append_row(["Nom", "Temps", "Secondes"])
    return sheet

def parse_time(time_str):
    """Accepts HH:MM:SS or H:MM:SS or MM:SS — returns total seconds."""
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
    """Convert seconds back to H:MM:SS."""
    h = seconds // 3600
    m = (seconds % 3600) // 60
    s = seconds % 60
    return f"{h}:{m:02d}:{s:02d}"

def load_data(sheet):
    records = sheet.get_all_records()
    if not records:
        return pd.DataFrame(columns=["Nom", "Temps", "Secondes"])
    df = pd.DataFrame(records)
    df["Secondes"] = pd.to_numeric(df["Secondes"], errors="coerce")
    return df

def medal(rank):
    if rank == 1: return "🥇"
    if rank == 2: return "🥈"
    if rank == 3: return "🥉"
    return f"#{rank}"

# ── UI ───────────────────────────────────────────────────────────────────────
st.markdown("# 🏃 Classement Marathon")
st.markdown("Entrez les résultats de votre équipe et voyez le classement en temps réel.")

try:
    sheet = get_sheet()

    # ── Add runner ────────────────────────────────────────────────────────────
    st.markdown("---")
    st.subheader("Ajouter un coureur")

    col1, col2 = st.columns([2, 1])
    with col1:
        nom = st.text_input("Nom du coureur", placeholder="Ex: Marie Tremblay")
    with col2:
        temps = st.text_input("Temps (H:MM:SS)", placeholder="Ex: 3:45:22")

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
                if nom.strip().lower() in df["Nom"].str.lower().values:
                    st.warning(f"⚠️ **{nom}** est déjà dans le classement.")
                else:
                    sheet.append_row([nom.strip(), seconds_to_str(secondes), secondes])
                    st.success(f"✅ **{nom}** ajouté avec un temps de **{seconds_to_str(secondes)}**!")
                    st.cache_resource.clear()
                    st.rerun()

    # ── Classement ────────────────────────────────────────────────────────────
    st.markdown("---")
    st.subheader("Classement")

    df = load_data(sheet)

    if df.empty or len(df) == 0:
        st.info("Aucun coureur pour l'instant. Ajoutez le premier résultat ci-dessus!")
    else:
        df_sorted = df.dropna(subset=["Secondes"]).sort_values("Secondes").reset_index(drop=True)

        # Stats rapides
        c1, c2, c3 = st.columns(3)
        c1.metric("Coureurs", len(df_sorted))
        c2.metric("Meilleur temps", df_sorted.iloc[0]["Temps"] if len(df_sorted) > 0 else "—")
        c3.metric("Temps moyen", seconds_to_str(int(df_sorted["Secondes"].mean())) if len(df_sorted) > 0 else "—")

        st.markdown("")

        # Tableau classement
        for i, row in df_sorted.iterrows():
            rank = i + 1
            bg = "#FFF9E6" if rank == 1 else "#F9F9F9" if rank % 2 == 0 else "#FFFFFF"
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
                    <span style="flex: 1; font-weight: {'600' if rank <= 3 else '400'};">{row['Nom']}</span>
                    <span style="font-family: monospace; font-size: 18px; color: #333;">{row['Temps']}</span>
                </div>
                """,
                unsafe_allow_html=True,
            )

    # ── Supprimer un coureur ─────────────────────────────────────────────────
    if not df.empty and len(df) > 0:
        st.markdown("---")
        with st.expander("🗑️ Supprimer un coureur"):
            noms_liste = df["Nom"].tolist()
            nom_suppr = st.selectbox("Choisir le coureur à supprimer", noms_liste)
            if st.button("Supprimer", type="secondary"):
                all_values = sheet.get_all_values()
                for i, row in enumerate(all_values):
                    if row[0] == nom_suppr:
                        sheet.delete_rows(i + 1)
                        st.success(f"**{nom_suppr}** supprimé.")
                        st.cache_resource.clear()
                        st.rerun()
                        break

except Exception as e:
    st.error(f"Erreur de connexion: {e}")
    st.info("Vérifiez que vos secrets Streamlit (gcp_service_account et sheet_name) sont bien configurés.")
