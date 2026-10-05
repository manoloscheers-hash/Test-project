import streamlit as st
import datetime
import pandas as pd
import plotly.express as px
from stravalib import Client

# Pagina instellingen
st.set_page_config(page_title="Running Load & Recovery Monitor", page_icon="🏃‍♂️", layout="centered")

st.title("🏃‍♂️ Running Hardloop & Herstel Monitor")
st.markdown("""
Analyseer je **Acute-to-Chronic Workload Ratio (ACWR)** en trainingsbelasting op basis van je eigen Strava-activiteiten.
""")

# Vaste Client ID en Secret (deze mag je delen, je geheime token deel je NIET meer)
DEFAULT_CLIENT_ID = 284865
DEFAULT_CLIENT_SECRET = "2812bd767959baabe261e8da78c2950565da4614"

# Invoerkeuze in de sidebar
st.sidebar.header("Data Bron & Invoer")
invoer_methode = st.sidebar.radio("Kies invoermethode:", ["Handmatig (Getallen)", "Strava API (Inloggen met Strava)"])

# --- SESSION STATE INITIALISATIE ---
if "access_token" not in st.session_state: st.session_state.access_token = None
if "refresh_token" not in st.session_state: st.session_state.refresh_token = None
if "max_hr" not in st.session_state: st.session_state.max_hr = 190
if "rest_hr" not in st.session_state: st.session_state.rest_hr = 45

weekly_loads = []
weekly_details = []
chart_df = None
parsed_activities = []

if invoer_methode == "Handmatig (Getallen)":
    st.sidebar.markdown("### Wekelijkse Belasting (Load Score)")
    w4 = st.sidebar.number_input("Week 4 (oudste)", min_value=0.0, max_value=1000.0, value=75.0, step=1.0)
    w3 = st.sidebar.number_input("Week 3", min_value=0.0, max_value=1000.0, value=80.0, step=1.0)
    w2 = st.sidebar.number_input("Week 2", min_value=0.0, max_value=1000.0, value=85.0, step=1.0)
    w1 = st.sidebar.number_input("Week 1 (vorige week)", min_value=0.0, max_value=1000.0, value=90.0, step=1.0)
    current_week = st.sidebar.number_input("Huidige week (meest recent)", min_value=0.0, max_value=1000.0, value=105.0,
                                           step=1.0)

    weekly_loads = [w4, w3, w2, w1, current_week]
    acute_load = current_week
    chronic_load = sum(weekly_loads[:-1]) / len(weekly_loads[:-1])

    dummy_dates = [datetime.date.today() - datetime.timedelta(weeks=i) for i in range(4, -1, -1)]
    chart_df = pd.DataFrame({"Datum": dummy_dates, "Trainingsbelasting": weekly_loads})

    weekly_details = [
        {"Week Start": dummy_dates[i].strftime("%d %b %Y"), "Totale Afstand (km)": [12.0, 15.0, 16.0, 18.0, 20.0][i],
         "Gem. Hartslag (bpm)": [145, 148, 142, 150, 152][i], "Totale Tijd (min)": [60.0, 75.0, 80.0, 90.0, 100.0][i],
         "Trainingsbelasting (Load)": weekly_loads[i]}
        for i in range(5)
    ]

else:
    st.sidebar.markdown("### Strava Authenticatie")

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
            # Schoon de URL op van de code
            st.query_params.clear()
            st.rerun()
        except Exception as e:
            st.sidebar.error(f"Fout bij uitwisselen autorisatiecode: {e}")

    # Als we nog geen access token hebben, toon de inloglink
    if not st.session_state.access_token:
        redirect_uri = "http://localhost:8501"  # Pas dit aan naar je publieke URL als je hem online host (bijv. Streamlit Cloud)
        authorize_url = client.authorization_url(
            client_id=DEFAULT_CLIENT_ID,
            redirect_uri=redirect_uri,
            scope=['read', 'activity:read_all']
        )
        st.sidebar.markdown(f"👉 **[Klik hier om in te loggen met Strava]({authorize_url})**")
        st.warning("Log links in via de sidebar met je eigen Strava-account om je data te laden.")

        # Standaard fallback data om de UI gevuld te houden
        weekly_loads = [75.0, 80.0, 85.0, 90.0, 105.0]
        acute_load = 105.0
        chronic_load = 82.5
        dummy_dates = [datetime.date.today() - datetime.timedelta(weeks=i) for i in range(4, -1, -1)]
        chart_df = pd.DataFrame({"Datum": dummy_dates, "Trainingsbelasting": weekly_loads})

    else:
        st.sidebar.success("Succesvol ingelogd met Strava! ✅")
        if st.sidebar.button("Uitloggen / Account wisselen"):
            st.session_state.access_token = None
            st.session_state.refresh_token = None
            st.rerun()

        st.sidebar.markdown("---")
        st.sidebar.markdown("### ⚙️ Fysiologische Instellingen")
        max_hr_input = st.sidebar.number_input("Maximale Hartslag (bpm)", min_value=120, max_value=220,
                                               value=st.session_state.max_hr)
        rest_hr_input = st.sidebar.number_input("Rusthartslag (bpm)", min_value=30, max_value=90,
                                                value=st.session_state.rest_hr)

        st.session_state.max_hr = max_hr_input
        st.session_state.rest_hr = rest_hr_input

        st.sidebar.markdown("---")
        st.sidebar.markdown("### 📅 Tijdweergave & Analyse")
        tijd_optie = st.sidebar.selectbox(
            "Selecteer tijdsbereik:",
            ["Laatste 4 Wekelijkse (Standaard ACWR)", "Afgelopen 3 Maanden", "Afgelopen 6 Maanden",
             "Afgelopen Jaar (12 Maanden)"]
        )

        if tijd_optie == "Laatste 4 Wekelijkse (Standaard ACWR)":
            aantal_weken = 5
        elif tijd_optie == "Afgelopen 3 Maanden":
            aantal_weken = 13
        elif tijd_optie == "Afgelopen 6 Maanden":
            aantal_weken = 26
        else:
            aantal_weken = 52

        try:
            client.access_token = st.session_state.access_token

            now = datetime.datetime.now(datetime.timezone.utc)
            start_date = now - datetime.timedelta(weeks=aantal_weken)

            activities = list(client.get_activities(after=start_date))
            st.sidebar.info(f"{len(activities)} activiteiten opgehaald uit jouw Strava.")

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
            chronic_load = sum(chronic_loads_list) / 4.0 if sum(chronic_loads_list) > 0 else 82.5

            chart_df = pd.DataFrame({"Datum": sorted_dates, "Trainingsbelasting": weekly_loads})

            weekly_details = []
            for m in sorted_dates:
                d = raw_weeks[m]
                avg_h = sum(d["hrs"]) / len(d["hrs"]) if d["hrs"] else 0.0
                weekly_details.append({
                    "Week Start": m.strftime("%d %b %Y"),
                    "Totale Afstand (km)": round(d["dist"], 1),
                    "Gem. Hartslag (bpm)": round(avg_h, 1) if avg_h > 0 else "N.B.",
                    "Totale Tijd (min)": round(d["times"], 1),
                    "Trainingsbelasting (Load)": round(d["load"], 1)
                })
        except Exception as e:
            st.error(f"Fout bij ophalen Strava data: {e}")
            weekly_loads = [75.0, 80.0, 85.0, 90.0, 105.0]
            acute_load = 105.0
            chronic_load = 82.5
            dummy_dates = [datetime.date.today() - datetime.timedelta(weeks=i) for i in range(4, -1, -1)]
            chart_df = pd.DataFrame({"Datum": dummy_dates, "Trainingsbelasting": weekly_loads})

# --- Berekening logica (ACWR) ---
if len(weekly_loads) >= 1:
    acwr = acute_load / chronic_load if chronic_load > 0 else 0

    st.subheader("📊 Belasting & Herstel Analyse (Rollende 7 Dagen)")
    col1, col2, col3 = st.columns(3)
    col1.metric("Acute Load (Afgelopen 7d)", f"{round(acute_load, 1)}")
    col2.metric("Chronic Load (Gem. 4 weken)", f"{round(chronic_load, 1)}")
    col3.metric("ACWR Ratio", f"{round(acwr, 2)}")

    st.markdown("### Advies & Blessurerisico")
    if acwr < 0.8:
        st.info(
            "⚠️ **Ondertraining:** Je trainingsbelasting van de afgelopen 7 dagen is aan de lage kant vergeleken met je baseline.")
    elif 0.8 <= acwr <= 1.3:
        st.success(
            "🟢 **Optimaal ('Sweet Spot'):** Je opbouw is veilig, progressief en optimaal voor prestatieverbetering!")
    elif 1.3 < acwr <= 1.5:
        st.warning(
            "🟠 **Verhoogd risico:** Je intensiteit/volume maakt een flinke piek ten opzichte van je baseline. Zorg voor voldoende herstel.")
    else:
        st.error("🔴 **Gevaarlijke zone:** Hoge kans op overbelasting! Overweeg gas terug te nemen.")

    st.subheader(f"📈 Trend in Trainingsbelasting per Week")
    if chart_df is not None:
        fig = px.line(
            chart_df, x="Datum", y="Trainingsbelasting", markers=True,
            labels={"Datum": "Week Startdatum", "Trainingsbelasting": "Belasting (Load)"}
        )
        fig.update_layout(xaxis_type="date", margin=dict(l=20, r=20, t=20, b=20))
        st.plotly_chart(fig, use_container_width=True)

    if weekly_details:
        st.subheader("📋 Gedetailleerd Overzicht per Week")
        df_details = pd.DataFrame(weekly_details)
        st.dataframe(df_details.iloc[::-1], use_container_width=True)