import streamlit as st
import datetime
import pandas as pd
import plotly.express as px
from stravalib import Client

# 1. Pagina instellingen (Geoptimaliseerd voor mobiel: gebruik 'wide' of compacte elementen)
st.set_page_config(
    page_title="Hardloop Monitor",
    page_icon="🏃‍♂️",
    layout="centered",
    initial_sidebar_state="expanded"
)

# Mobielvriendelijke CSS stijlen om metrische kaartjes op kleine schermen mooi te tonen
st.markdown("""
    <style>
    [data-testid="stMetricValue"] {
        font-size: 24px;
    }
    .main {
        padding-top: 0rem;
    }
    </style>
""", unsafe_allow_html=True)

st.title("🏃‍♂️ Hardloop monitor")
st.markdown("Monitor je trainingsbelasting en blessurerisico op basis van je Strava-activiteiten.")

# Vaste Client ID en Secret
DEFAULT_CLIENT_ID = 284865
DEFAULT_CLIENT_SECRET = "2812bd767959baabe261e8da78c2950565da4614"

# --- SESSION STATE INITIALISATIE ---
if "access_token" not in st.session_state: st.session_state.access_token = None
if "refresh_token" not in st.session_state: st.session_state.refresh_token = None
if "max_hr" not in st.session_state: st.session_state.max_hr = 190
if "rest_hr" not in st.session_state: st.session_state.rest_hr = 45

# --- STRAVA AUTHENTICATIE ---
client = Client()

# Check of de URL een autorisatiecode bevat (terugkomst van Strava inlogpagina)
query_params = st.query_params
if "code" in query_params and not st.session_state.access_token:
    auth_code = query_params["code"]
    try:
        token_response = client.exchange_code_for_token(
            client_id=DEFAULT_CLIENT_ID,
            client_secret=DEFAULT_CLIENT_SECRET,
            code=auth_code
        )
        st.session_state.access_token = token_response['access_token']
        st.session_state.refresh_token = token_response['refresh_token']
        st.query_params.clear()
        st.rerun()
    except Exception as e:
        st.error(f"Fout bij uitwisselen autorisatiecode: {e}")

# Als we nog geen access token hebben, toon alleen de inlogknop
if not st.session_state.access_token:
    st.info("👋 Welkom! Log in met je Strava-account om je eigen hardloopdata te analyseren.")

    redirect_uri = "https://test-project-esbc6cm8557nybkrc4o8kv.streamlit.app"
    authorize_url = client.authorization_url(
        client_id=DEFAULT_CLIENT_ID,
        redirect_uri=redirect_uri,
        scope=['read', 'activity:read_all']
    )

    # Grote, goed zichtbare inlogknop voor mobiel
    st.markdown(
        f"""
        <div style="text-align: center; margin-top: 30px; margin-bottom: 30px;">
            <a href="{authorize_url}" target="_self" style="background-color: #fc4c02; color: white; padding: 15px 25px; text-decoration: none; font-size: 18px; font-weight: bold; border-radius: 5px; box-shadow: 0px 4px 6px rgba(0,0,0,0.1);">
                🔗 Inloggen met Strava
            </a>
        </div>
        """,
        unsafe_allow_html=True
    )

else:
    # --- ZIJBALK VOOR INSTELLINGEN ---
    st.sidebar.markdown("### ⚙️ Profiel & Instellingen")

    # Hartslag instellingen worden opgeslagen in de sessie van de ingelogde gebruiker
    max_hr_input = st.sidebar.number_input("Maximale Hartslag (bpm)", min_value=120, max_value=220,
                                           value=st.session_state.max_hr)
    rest_hr_input = st.sidebar.number_input("Rusthartslag (bpm)", min_value=30, max_value=90,
                                            value=st.session_state.rest_hr)

    st.session_state.max_hr = max_hr_input
    st.session_state.rest_hr = rest_hr_input

    st.sidebar.markdown("---")
    tijd_optie = st.sidebar.selectbox(
        "📅 Tijdweergave analyse:",
        ["Laatste 4 Wekelijkse (Standaard ACWR)", "Afgelopen 3 Maanden", "Afgelopen 6 Maanden", "Afgelopen Jaar"]
    )

    if tijd_optie == "Laatste 4 Wekelijkse (Standaard ACWR)":
        aantal_weken = 5
    elif tijd_optie == "Afgelopen 3 Maanden":
        aantal_weken = 13
    elif tijd_optie == "Afgelopen 6 Maanden":
        aantal_weken = 26
    else:
        aantal_weken = 52

    if st.sidebar.button("Uitloggen / Account wisselen", use_container_width=True):
        st.session_state.access_token = None
        st.session_state.refresh_token = None
        st.rerun()

    # --- DATA OPHALEN & BEREKENEN ---
    try:
        client.access_token = st.session_state.access_token

        now = datetime.datetime.now(datetime.timezone.utc)
        start_date = now - datetime.timedelta(weeks=aantal_weken)

        with st.spinner("Je Strava-activiteiten ophalen... 🏃‍♂️"):
            activities = list(client.get_activities(after=start_date))

        weeks_list = []
        for i in range(aantal_weken - 1, -1, -1):
            d = now - datetime.timedelta(weeks=i)
            monday = d - datetime.timedelta(days=d.weekday())
            weeks_list.append(monday.date())

        raw_weeks = {m_date: {"dist": 0.0, "load": 0.0, "hrs": [], "times": 0.0} for m_date in weeks_list}
        parsed_activities = []

        for act in activities:
            if act.type and 'Run' in str(act.type):
                act_date = act.start_date
                if act_date:
                    dist_meters = float(act.distance) if act.distance else 0.0
                    dist_km = dist_meters / 1000.0

                    moving_time_mins = 0.0
                    time_source = getattr(act, 'moving_time', None) or getattr(act, 'elapsed_time', None)
                    if time_source:
                        try:
                            moving_time_mins = time_source.total_seconds() / 60.0
                        except:
                            moving_time_mins = float(time_source) / 60.0 if time_source else 0.0

                    if moving_time_mins <= 0 and dist_km > 0:
                        moving_time_mins = dist_km * 5.0

                    avg_hr = float(act.average_heartrate) if hasattr(act,
                                                                     'average_heartrate') and act.average_heartrate else 0.0

                    # Bereken trainingsbelasting op basis van de ingestelde maximale/rust hartslag van de gebruiker
                    if avg_hr > st.session_state.rest_hr and st.session_state.max_hr > st.session_state.rest_hr:
                        hr_reserve_ratio = (avg_hr - st.session_state.rest_hr) / (
                                    st.session_state.max_hr - st.session_state.rest_hr)
                        training_load = moving_time_mins * (hr_reserve_ratio * 1.5)
                    else:
                        training_load = dist_km * 10

                    parsed_activities.append({"datetime": act_date, "load": training_load})

                    act_monday = (act_date - datetime.timedelta(days=act_date.weekday())).date()
                    if act_monday in raw_weeks:
                        if avg_hr > 0:
                            raw_weeks[act_monday]["hrs"].append(avg_hr)
                        raw_weeks[act_monday]["dist"] += dist_km
                        raw_weeks[act_monday]["load"] += training_load
                        raw_weeks[act_monday]["times"] += moving_time_mins

        sorted_dates = sorted(raw_weeks.keys())
        weekly_loads = [round(raw_weeks[m]["load"], 1) for m in sorted_dates]

        cutoff_acute = now - datetime.timedelta(days=7)
        acute_load = sum([a["load"] for a in parsed_activities if a["datetime"] >= cutoff_acute])

        chronic_loads_list = [
            sum([a["load"] for a in parsed_activities if (now - datetime.timedelta(days=w * 7)) > a["datetime"] >= (
                        now - datetime.timedelta(days=(w + 1) * 7))])
            for w in range(1, 5)
        ]
        chronic_load = sum(chronic_loads_list) / 4.0 if sum(chronic_loads_list) > 0 else 1.0

        chart_df = pd.DataFrame({"Datum": sorted_dates, "Trainingsbelasting": weekly_loads})

        weekly_details = []
        for m in sorted_dates:
            d = raw_weeks[m]
            avg_h = sum(d["hrs"]) / len(d["hrs"]) if d["hrs"] else 0.0
            weekly_details.append({
                "Week Start": m.strftime("%d %b"),
                "Afstand (km)": round(d["dist"], 1),
                "Gem. HR": round(avg_h, 1) if avg_h > 0 else "N.B.",
                "Tijd (min)": round(d["times"], 1),
                "Load": round(d["load"], 1)
            })

        # --- DASHBOARD WEERGAVE (MOBIEL VRIENDELIJK) ---
        acwr = acute_load / chronic_load if chronic_load > 0 else 0

        st.subheader("📊 ACWR Overzicht")

        # Op mobiel stacken kolommen automatisch mooi onder elkaar of naast elkaar
        col1, col2, col3 = st.columns(3)
        col1.metric("Acute (7d)", f"{round(acute_load, 1)}")
        col2.metric("Chronic (4w)", f"{round(chronic_load, 1)}")
        col3.metric("Ratio", f"{round(acwr, 2)}")

        # Advies box
        if acwr < 0.8:
            st.info("⚠️ **Ondertraining:** Je belasting is vrij laag vergeleken met je baseline.")
        elif 0.8 <= acwr <= 1.3:
            st.success("🟢 **Optimaal:** Veilige opbouw, perfect voor progressie!")
        elif 1.3 < acwr <= 1.5:
            st.warning("🟠 **Let op:** Snelle piek in belasting. Bouw voldoende rust in.")
        else:
            st.error("🔴 **Hoog risico:** Grote kans op overbelasting! Doe rustig aan.")

        st.subheader("📈 Wekelijkse Belasting")
        fig = px.line(
            chart_df, x="Datum", y="Trainingsbelasting", markers=True,
            labels={"Datum": "Datum", "Trainingsbelasting": "Load"}
        )
        fig.update_layout(
            xaxis_type="date",
            margin=dict(l=10, r=10, t=10, b=10),
            height=300
        )
        st.plotly_chart(fig, use_container_width=True)

        if weekly_details:
            st.subheader("📋 Historie per week")
            df_details = pd.DataFrame(weekly_details)
            st.dataframe(df_details.iloc[::-1], use_container_width=True, hide_index=True)

    except Exception as e:
        st.error(f"Er ging iets mis bij het ophalen van je Strava-activiteiten: {e}")