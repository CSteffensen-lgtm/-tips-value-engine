import os
import pandas as pd
import streamlit as st
from dotenv import load_dotenv

from connectors.odds_api import fetch_soccer_odds
from engine.value import analyze_matches
from engine.backtest import brier_score
from connectors.danskespil import parse_danskespil_payload, save_snapshot, snapshot_count
import json
from pathlib import Path

load_dotenv()
st.set_page_config(page_title="Tips Value Engine", page_icon="⚽", layout="wide")

st.title("⚽ Tips Value Engine")
st.caption("MVP 1.0 · Sandsynligheder, markedsværdi, spillerpopularitet og kuponbudget")

with st.sidebar:
    st.header("Indstillinger")
    budget = st.number_input("Budget pr. kupon (kr.)", min_value=10.0, max_value=1000.0, value=75.0, step=5.0)
    row_price = st.number_input("Pris pr. række (kr.)", min_value=0.01, value=1.0, step=0.25)
    sport_key = st.selectbox("Liga", ["soccer_epl", "soccer_spain_la_liga", "soccer_germany_bundesliga", "soccer_italy_serie_a", "soccer_france_ligue_one"], format_func=lambda x: {
        "soccer_epl":"Premier League", "soccer_spain_la_liga":"La Liga",
        "soccer_germany_bundesliga":"Bundesliga", "soccer_italy_serie_a":"Serie A",
        "soccer_france_ligue_one":"Ligue 1"}[x])
    st.caption("Odds kræver en The Odds API-nøgle i .env. Spillerprocenter importeres separat.")

tab1, tab2, tab3, tab4, tab5 = st.tabs(["Live analyse", "Danske Spil-data", "Spillerprocenter", "Kuponbygger", "Backtest"])

@st.cache_data(ttl=300, show_spinner=False)
def load_live(key, league):
    return fetch_soccer_odds(key, league)

with tab1:
    st.subheader("Kampdata og markedsodds")
    api_key = os.getenv("THE_ODDS_API_KEY", "").strip()
    c1, c2 = st.columns([1, 3])
    with c1:
        refresh = st.button("Hent aktuelle odds", type="primary")
    if refresh:
        st.cache_data.clear()
    if api_key:
        try:
            live = load_live(api_key, sport_key)
            if live.empty:
                st.info("API'en returnerede ingen kommende kampe for den valgte liga.")
            else:
                st.success(f"Hentede {len(live)} kampe. Odds er bookmakerdata, ikke Danske Spils Tips-procenter.")
                st.dataframe(live, use_container_width=True, hide_index=True)
                st.download_button("Download kampdata CSV", live.to_csv(index=False).encode("utf-8"), "tips_live_odds.csv", "text/csv")
        except Exception as e:
            st.error(f"Kunne ikke hente odds: {e}")
            live = pd.DataFrame()
    else:
        st.warning("Ingen API-nøgle fundet. Du kan stadig teste modellen med eksempeldata eller CSV.")
        live = pd.DataFrame()

    st.markdown("#### Upload kampdata")
    uploaded = st.file_uploader("CSV med odds og eventuelt spillerprocenter", type=["csv"], key="live_csv")
    if uploaded:
        try:
            df = pd.read_csv(uploaded)
            analyzed = analyze_matches(df)
            st.dataframe(analyzed, use_container_width=True, hide_index=True)
            st.download_button("Download analyseresultat", analyzed.to_csv(index=False).encode("utf-8"), "tips_value_analysis.csv", "text/csv")
        except Exception as e:
            st.error(f"CSV kunne ikke analyseres: {e}")

    if st.button("Indlæs eksempeldata"):
        sample_path = Path(__file__).resolve().parent / "data" / "sample_matches.csv"
        sample = pd.read_csv(sample_path)
        st.session_state["sample_analysis"] = analyze_matches(sample)
    if "sample_analysis" in st.session_state:
        st.dataframe(st.session_state["sample_analysis"], use_container_width=True, hide_index=True)

with tab2:
    st.subheader("Danske Spil – dataindsamling")
    st.write("Første connector-version kan parse og gemme kupon- og kampdata. Automatisk live-hentning er endnu ikke slået til, fordi API-host, kupon-discovery og adgangsvilkår skal verificeres på tværs af kuponformater.")
    st.metric("Gemte data-snapshots", snapshot_count())
    st.markdown("#### Importér rå API-svar til validering")
    st.caption("Upload JSON-responsen fra pools-endpointet og events-by-ids-endpointet. Fjern personlige oplysninger og eventuelle tokens/headers; upload aldrig cookies eller loginoplysninger.")
    pool_json = st.file_uploader("Pools JSON", type=["json"], key="ds_pool_json")
    events_json = st.file_uploader("Events-by-ids JSON", type=["json"], key="ds_events_json")
    if pool_json and events_json:
        try:
            pool_payload = json.load(pool_json)
            events_payload = json.load(events_json)
            metadata, ds_matches = parse_danskespil_payload(pool_payload, events_payload)
            st.success(f"Kupondata genkendt: {metadata.get('name')} · {metadata.get('type')} · {len(ds_matches)} kampe")
            st.json({k: v for k, v in metadata.items() if k != "poolPrizes"})
            st.dataframe(ds_matches, use_container_width=True, hide_index=True)
            if st.button("Gem snapshot i historikken", type="primary"):
                sid = save_snapshot(metadata, ds_matches)
                st.success(f"Snapshot gemt (ID {sid}).")
        except Exception as e:
            st.error(f"Kunne ikke parse Danske Spil-data: {e}")
    st.info("Næste trin er at bekræfte de præcise offentlige request-URL'er og om de kan bruges uden login. Vi automatiserer ikke adgang via cookies, MitID eller private sessioner.")

with tab3:
    st.subheader("Spillerpopularitet")
    st.write("Indlæs de faktiske 1/X/2-procenter fra den aktuelle Tips-kupon. Vi holder dem adskilt fra bookmakerodds.")
    pop_file = st.file_uploader("Upload spillerprocenter CSV", type=["csv"], key="pop_csv")
    st.code("match,players_1,players_x,players_2\nArsenal - Chelsea,0.62,0.23,0.15", language="csv")
    if pop_file:
        try:
            pop = pd.read_csv(pop_file)
            required = {"match", "players_1", "players_x", "players_2"}
            if not required.issubset(pop.columns):
                st.error(f"Mangler kolonner: {sorted(required - set(pop.columns))}")
            else:
                st.dataframe(pop, use_container_width=True, hide_index=True)
                st.success("Spillerprocenter indlæst. De kan sammenkobles med odds via kampnavn.")
        except Exception as e:
            st.error(str(e))

with tab4:
    st.subheader("Kuponbygger")
    st.write("MVP-optimering: vælg udfald med højeste modelværdi under et fast række-budget. R/U-garantier håndteres først, når konkrete officielle systemnøgler er indlæst.")
    n = st.number_input("Antal kampe", min_value=4, max_value=13, value=13)
    budget_rows = int(budget // row_price)
    st.metric("Maksimalt antal rækker inden for budget", budget_rows)
    st.info("For en fuld Tips-kupon skal systemvalget også tage højde for de officielle række- og garantiregler. Denne første version optimerer tegnvalg og budget, ikke en udokumenteret R/U-garanti.")
    if st.button("Vis optimeringsprincip"):
        st.write("Vi rangerer først kampudfaldene efter estimeret edge og popularitetsgab. Derefter prioriteres garderinger dér, hvor usikkerheden er størst, indtil budgettet er brugt.")

with tab5:
    st.subheader("Historisk backtest")
    hist = st.file_uploader("Upload backtest CSV", type=["csv"], key="backtest_csv")
    st.code("p1,px,p2,result\n0.50,0.25,0.25,1\n0.30,0.40,0.30,X", language="csv")
    if hist:
        try:
            h = pd.read_csv(hist)
            score = brier_score(h)
            st.metric("Multiclass Brier score", f"{score:.4f}")
            st.caption("Lavere er bedre. En score kan ikke vurderes uden sammenligning med en baseline og et tilstrækkeligt stort, tidsmæssigt adskilt datasæt.")
        except Exception as e:
            st.error(f"Backtest kunne ikke beregnes: {e}")

st.divider()
st.caption("Ansvarlig brug: Værdiindikatorer er estimater, ikke garantier. En positiv modelscore er ikke automatisk positiv forventet økonomisk værdi i et puljespil.")
