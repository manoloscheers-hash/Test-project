import streamlit as st
import datetime
import pandas as pd
import plotly.express as px
from stravalib import Client

# 1. Pagina instellingen
st.set_page_config(
    page_title="Running & Nutrition Monitor",
    page_icon="🏃‍♂️",
    layout="centered",
    initial_sidebar_state="expanded"
)

# Mobielvriendelijke CSS stijlen
st.markdown("""
    <style>
    [data-testid="stMetricValue"] {
        font-size: 22px;
    }
    @media (max-width: 768px) {
        h1 {
            font-size: 24px !important;
        }
    }
    .main {
        padding-top: 0rem;
    }
    </style>
""", unsafe_allow_html=True)

st.title("🏃‍♂️ Running & Herstel Monitor")
st.markdown("Monitor je trainingsbelasting en voedingsherstel op basis van je Strava-activiteiten.")

# Vaste Client ID en Secret
DEFAULT_CLIENT_ID = 284865
DEFAULT_CLIENT_SECRET = "2812bd767959baabe261e8da78c2950565da4614"

# --- SESSION STATE INITIALISATIE ---
if "access_token" not in st.session_state: st.session_state.access_token = None
if "refresh_token" not in st.session_state: st.session_state.refresh_token = None
if "max_hr" not in st.session_state: st.session_state.max_hr = 190
if "rest_hr" not in st.session_state: st.session_state.rest_hr = 45
if "body_weight" not in st.session_state: st.session_state.body_weight = 65.0  # Standaard gewicht in kg voor calorieberekening

# --- STRAVA AUTHENTICATIE ---
client = Client()

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

# Als we nog geen access token hebben, toon de inlogknop
if not st.session_state.access_token:
    st.info("👋 Welkom! Log in met je Strava-account om je eigen hardloopdata te analyseren.")

    redirect_uri = "https://test-project-esbc6cm8557nybkrc4o8kv.streamlit.app"
    authorize_url = client.authorization_url(
        client_id=DEFAULT_CLIENT_ID,
        redirect_uri=redirect_uri,
        scope=['read', 'activity:read_all']
    )

    st.link_button("🔗 Inloggen met Strava", authorize_url, use_container_width=True)

else:
    # --- ZIJBALK VOOR INSTELLINGEN ---
    st.sidebar.markdown("### ⚙️️ Profiel & Instellingen")

    max_hr_input = st.sidebar.number_input("Maximale Hartslag (bpm)", min_value=120, max_value=220,
                                           value=st.session_state.max_hr)
    rest_hr_input = st.sidebar.number_input("Rusthartslag (bpm)", min_value=30, max_value=90,
                                            value=st.session_state.rest_hr)
    weight_input = st.sidebar.number_input("Lichaamsgewicht (kg)", min_value=40.0, max_value=120.0,
                                           value=st.session_state.body_weight, step=0.5)

    st.session_state.max_hr = max_hr_input
    st.session_state.rest_hr = rest_hr_input
    st.session_state.body_weight = weight_input

    st.sidebar.markdown("---")
    tijd_optie = st.sidebar.selectbox(
        "📅 Tijdweergave analyse:",
        ["Laatste 4 Wekelijkse", "Afgelopen 3 Maanden", "Afgelopen 6 Maanden", "Afgelopen Jaar"]
    )

    if tijd_optie == "Laatste 4 Wekelijkse":
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

        raw_weeks = {m_date: {"dist": 0.0, "load": 0.0, "hrs": [], "times": 0.0, "cals": 0.0} for m_date in weeks_list}
        parsed_activities = []
        detailed_activities_list = []

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

                    # Trainingsbelasting berekening
                    if avg_hr > st.session_state.rest_hr and st.session_state.max_hr > st.session_state.rest_hr:
                        hr_reserve_ratio = (avg_hr - st.session_state.rest_hr) / (
                                    st.session_state.max_hr - st.session_state.rest_hr)
                        training_load = moving_time_mins * (hr_reserve_ratio * 1.5)
                    else:
                        training_load = dist_km * 10

                        # Calorieverbruik schatting (globaal hardlopen: ~1 kcal per kg per kilometer)
                    # Als Strava zelf calorieën meegeeft, pakken we die, anders schatten we het op basis van gewicht & afstand
                    strava_cals = float(getattr(act, 'kilojoules', 0) / 4.184) if hasattr(act,
                                                                                          'kilojoules') and act.kilojoules else 0.0
                    if strava_cals <= 0:
                        # Ruwe schatting: gewicht (kg) * afstand (km) * 1.03 kcal
                        estimated_cals = st.session_state.body_weight * dist_km * 1.03
                    else:
                        estimated_cals = strava_cals

                    parsed_activities.append({"datetime": act_date, "load": training_load})

                    # Bewaar voor het Voedingstabblad
                    act_name = getattr(act, 'name', 'Hardloopsessie')
                    detailed_activities_list.append({
                        "id": act.id,
                        "datetime": act_date,
                        "label": f"{act_date.strftime('%d-%m-%Y')} - {act_name} ({round(dist_km, 1)} km)",
                        "name": act_name,
                        "distance": round(dist_km, 2),
                        "time_mins": round(moving_time_mins, 1),
                        "calories": round(estimated_cals, 0)
                    })

                    act_monday = (act_date - datetime.timedelta(days=act_date.weekday())).date()
                    if act_monday in raw_weeks:
                        if avg_hr > 0:
                            raw_weeks[act_monday]["hrs"].append(avg_hr)
                        raw_weeks[act_monday]["dist"] += dist_km
                        raw_weeks[act_monday]["load"] += training_load
                        raw_weeks[act_monday]["times"] += moving_time_mins
                        raw_weeks[act_monday]["cals"] += estimated_cals

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
                "Kcal": round(d["cals"], 0),
                "Load": round(d["load"], 1)
            })

        # --- TABS MAKEN VOOR NAVIGATIE ---
        tab_acwr, tab_nutrition = st.tabs(["📊 Belasting", "🍎 Voeding & Herstel"])

        with tab_acwr:
            acwr = acute_load / chronic_load if chronic_load > 0 else 0

            st.subheader("📊 Belasting Overzicht")
            col1, col2, col3 = st.columns(3)
            col1.metric("Acute (7d)", f"{round(acute_load, 1)}")
            col2.metric("Chronic (4w)", f"{round(chronic_load, 1)}")
            col3.metric("Ratio", f"{round(acwr, 2)}")

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

        with tab_nutrition:
            st.subheader("🍎 Voeding & Hersteladvies per Training")
            st.markdown(
                "Selecteer hieronder een recente training om het calorieverbruik, de hersteltijd en gerichte maaltijdvoorbeelden te bekijken.")

            if detailed_activities_list:
                # Filter alleen activiteiten van de afgelopen 7 dagen voor het voedingstabblad
                cutoff_7d = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=7)
                recent_acts = [act for act in detailed_activities_list if act["datetime"] >= cutoff_7d]

                if recent_acts:
                    activity_labels = [act["label"] for act in recent_acts]
                    chosen_label = st.selectbox("Kies een training (afgelopen 7 dagen):", activity_labels)
                    selected_act = next(act for act in recent_acts if act["label"] == chosen_label)
                else:
                    st.info(
                        "Je hebt in de afgelopen 7 dagen geen hardloopactiviteiten geregistreerd. Hier is je meest recente training:")
                    activity_labels = [act["label"] for act in detailed_activities_list[:5]]
                    chosen_label = st.selectbox("Kies een training:", activity_labels)
                    selected_act = next(act for act in detailed_activities_list if act["label"] == chosen_label)
                st.markdown("---")
                col_n1, col_n2, col_n3 = st.columns(3)
                col_n1.metric("Afstand", f"{selected_act['distance']} km")
                col_n2.metric("Duur", f"{selected_act['time_mins']} min")
                col_n3.metric("Verbrande Kcal", f"{selected_act['calories']} kcal")

                cals = selected_act['calories']
                duration = selected_act['time_mins']
                name_lower = selected_act['name'].lower()

                # --- 1. AUTOMATISCHE HERSTELTIJD INDICATOR ---
                # Bepaal intensiteit op basis van naam of calorieverbruik per minuut
                cals_per_min = cals / duration if duration > 0 else 10

                if any(k in name_lower for k in ["interval", "tempo", "VO2", "race", "wedstrijd", "sprint"] or cals_per_min > 13
                       ["interval", "tempo", "VO2", "race", "wedstrijd", "sprint"]) or cals_per_min > 13:
                    training_type = "Intensief (Interval / Tempo)"
                    recovery_hours = 48
                    recovery_status = "🔴 Zware belasting — Volledig glycogeenherstel en spierherstel vereist."
                elif selected_act['distance'] > 15 or duration > 75:
                    training_type = "Lange Duurloop (LSD)"
                    recovery_hours = 36
                    recovery_status = "🟠 Grote duurbelasting — Focus op vocht, zouten en langzame koolhydraten."
                else:
                    training_type = "Herstel / Rustige Duurloop"
                    recovery_hours = 24
                    recovery_status = "🟢 Lichte belasting — Snelle en eenvoudige hersteltijd."

                st.markdown("### ⏱️ Geschatte Hersteltijd")
                st.info(
                    f"**Type sessie:** {training_type}\n\n**Advies:** {recovery_status} \n*Geschatte tijd tot volledig herstel: **ca. {recovery_hours} uur**.*")

                # --- 2. DOELGERICHTE MACRO'S ---
                carbs_target = int(cals * 0.6 / 4)
                protein_target = int(st.session_state.body_weight * 0.3)

                st.markdown("### 🎯 Hersteldoel voor deze sessie")
                st.markdown(f"- **Koolhydraten aanvullen:** ca. **{carbs_target} gram**")
                st.markdown(f"- **Eiwitten voor spierherstel:** ca. **{protein_target} gram**")

                st.markdown("---")
                st.markdown("### 🍳 Intensiteits-specifieke Voorbeeldmaaltijden")

                # --- 3. DYNAMISCHE & GESCHAALDE VOORBEELDMAALTIJDEN ---
                # We schalen de maaltijden op basis van het verbrande aantal calorieën (doel is om de verbranding aan te vullen)

                if training_type == "Intensief (Interval / Tempo)":
                    # Reken portiewaarden uit op basis van totale verbranding (ongeveer 60% van cals moet uit koolhydraten komen)
                    c_maaltijd_1 = int(cals * 0.25)
                    c_maaltijd_2 = int(cals * 0.45)
                    c_maaltijd_3 = int(cals * 0.30)

                    st.markdown(f"""
                                    *Na een intensieve prikkel (verbranding: {cals} kcal) hebben je spieren directe herstelingrediënten nodig. De onderstaande maaltijden zijn exact afgestemd op jouw sessie van vandaag:*

                                    **1. De Snelle Post-Workout Smoothie (Direct na training)**
                                    * **Energie:** ca. **{c_maaltijd_1} kcal** | Koolhydraten: ~{int(c_maaltijd_1 * 0.65 / 4)}g | Eiwitten: ~{int(c_maaltijd_1 * 0.25 / 4)}g
                                    * *Wat:* 1 grote banaan, 300ml havermelk, 1.5 schep eiwitpoeder en een hand bosbessen.
                                    * *Waarom:* Snelle suikers en direct opneembare eiwitten om glycogeen en spierschade direct aan te pakken.

                                    **2. Hoofdmaaltijd: Rijst met Kip en Zoete Aardappel**
                                    * **Energie:** ca. **{c_maaltijd_2} kcal** | Koolhydraten: ~{int(c_maaltijd_2 * 0.60 / 4)}g | Eiwitten: ~{int(c_maaltijd_2 * 0.25 / 4)}g
                                    * *Wat:* Ruime portie witte rijst/zoete aardappel ({int(c_maaltijd_2 * 0.15)}g droog gewicht), 150g kipfilet, broccoliroosjes en olijfolie.
                                    * *Waarom:* Grote hoeveelheid snelle koolhydraten en eiwitten die precies past bij de zwaarte van deze intervaltraining.

                                    **3. Avondsnack / Herstelmaaltijd: Volkoren Pannenkoeken**
                                    * **Energie:** ca. **{c_maaltijd_3} kcal** | Koolhydraten: ~{int(c_maaltijd_3 * 0.55 / 4)}g | Eiwitten: ~{int(c_maaltijd_3 * 0.20 / 4)}g
                                    * *Wat:* 3 volkoren pannenkoeken met een ei, melk, rijkelijk overgoten met honing en banaan.
                                    * *Waarom:* Vult de resterende energievraag aan voor een complete nachtenlijke rust en spieropbouw.
                                    """)

                elif training_type == "Lange Duurloop (LSD)":
                    c_maaltijd_1 = int(cals * 0.30)
                    c_maaltijd_2 = int(cals * 0.45)
                    c_maaltijd_3 = int(cals * 0.25)

                    st.markdown(f"""
                                    *Tijdens deze lange duurloop ({selected_act['distance']} km / {cals} kcal) zijn je glycogeenreserves diep aangesproken. De maaltijden hieronder leveren langzame energie en de nodige zouten:*

                                    **1. De Power Havermoutkom (Ochtend / Post-run)**
                                    * **Energie:** ca. **{c_maaltijd_1} kcal** | Koolhydraten: ~{int(c_maaltijd_1 * 0.60 / 4)}g | Eiwitten: ~{int(c_maaltijd_1 * 0.20 / 4)}g
                                    * *Wat:* Flinke portie havermout in melk, 1.5 el pindakaas, gesneden appel, kaneel en een handje ongezouten noten.
                                    * *Waarom:* Langzame koolhydraten voor langdurige afgifte en gezonde vetten voor je herstel.

                                    **2. Hoofdmaaltijd: Volkoren Pasta Bolognese (Rijk aan groenten)**
                                    * **Energie:** ca. **{c_maaltijd_2} kcal** | Koolhydraten: ~{int(c_maaltijd_2 * 0.60 / 4)}g | Eiwitten: ~{int(c_maaltijd_2 * 0.25 / 4)}g
                                    * *Wat:* Ruime portie volkoren pasta, tomatensaus met veel groenten (paprika, courgette) en mager rundergehakt/linzen.
                                    * *Waarom:* Vult de enorme koolhydraatvoorraad weer aan en levert ijzer en bouwstoffen.

                                    **3. Geroosterde Volkoren Boterhammen met Avocado & Eieren**
                                    * **Energie:** ca. **{c_maaltijd_3} kcal** | Koolhydraten: ~{int(c_maaltijd_3 * 0.45 / 4)}g | Eiwitten: ~{int(c_maaltijd_3 * 0.25 / 4)}g
                                    * *Wat:* Sneetjes volkoren brood, geprakte avocado, 2 eieren en een snuf zeezout (voor zoutaanvulling na het zweten).
                                    * *Waarom:* Vezels, eiwitten en broodnodige natrium/zouten.
                                    """)


                else:
                    st.markdown(f"""
                    *Bij een lichte of herstelloop is de schade minimaal; je hoeft minder agressief aan te vullen, maar eiwitten blijven belangrijk.*

                    **1. Magere Kwark met Fruit en Noten**
                    * *Wat:* 250g magere kwark met een handje muesli, rood fruit en een handje walnoten.
                    * *Waarom:* Hoog in caseïne-eiwitten voor langdurig spierherstel zonder overbodige suikers.

                    **2. Omelet met Volkoren Brood**
                    * *Wat:* 2 eieren gebakken met spinazie en tomaat, geserveerd op 2 sneetjes volkoren brood.
                    * *Waarom:* Lichte, eiwitrijke maaltijd die je spieren voedt zonder dat het zwaar op de maag ligt.

                    **3. Salade met Quinoa en Tonijn**
                    * *Wat:* Kom quinoa, komkommer, tomaat, een blikje tonijn en een dressing van olijfolie en citroen.
                    * *Waarom:* Lichte koolhydraten en gezonde vetten/eiwitten voor een vlot herstel.
                    """)
            else:
                st.warning("Geen recente hardloopactiviteiten gevonden.")
    except Exception as e:
        st.error(f"Er ging iets mis bij het ophalen van je Strava-activiteiten: {e}")
        st.plotly_chart(fig, use_container_width=True)

        if weekly_details:
            st.subheader("📋 Historie per week")
            df_details = pd.DataFrame(weekly_details)
            st.dataframe(df_details.iloc[::-1], use_container_width=True, hide_index=True)

    except Exception as e:
        st.error(f"Er ging iets mis bij het ophalen van je Strava-activiteiten: {e}")