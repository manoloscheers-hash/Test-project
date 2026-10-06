import streamlit as st
import datetime
import pandas as pd
import plotly.express as px
from stravalib import Client
from streamlit_cropper import st_cropper
from PIL import Image

# 1. Pagina instellingen
st.set_page_config(
    page_title="Hardloop & Voedings Monitor",
    page_icon="🏃‍♂️",
    layout="centered",
    initial_sidebar_state="expanded"
)
st.markdown("""
    <style>
    /* 1. Algemene layout en rustige witruimte */
    .block-container {
        padding-top: 2rem;
        padding-bottom: 2rem;
        max-width: 1200px;
    }

    /* 2. Signatuur knoppen met subtiele hover-animatie */
    div.stButton > button {
        border-radius: 8px;
        font-weight: 500;
        border: 1px solid rgba(150, 150, 150, 0.2);
        transition: all 0.2s ease-in-out;
    }

    div.stButton > button:hover {
        border-color: #FF334B;
        color: #FF334B;
        box-shadow: 0 2px 6px rgba(255, 51, 75, 0.15);
    }

    /* 3. Actieve tabbladen voorzien van een strak accent */
    .stTabs [data-baseweb="tab-list"] button[aria-selected="true"] {
        color: #FF334B !important;
        border-bottom-color: #FF334B !important;
    }

    /* 4. Subtiele kaart-containers die zich aanpassen aan Light/Dark mode */
    div[data-testid="stMetric"], div[data-testid="stVerticalBlock"] > div[style*="border-color"] {
        border-radius: 10px;
        padding: 12px;
        border: 1px solid rgba(150, 150, 150, 0.15);
        box-shadow: 0 1px 3px rgba(0, 0, 0, 0.05);
    }
    </style>
""", unsafe_allow_html=True)

st.markdown("""
    <style>
    /* Algemene rustige achtergrond en strakke marges */
    .block-container {
        padding-top: 2rem;
        padding-bottom: 2rem;
    }

    /* Knoppen een moderne, zachte uitstraling geven */
    div.stButton > button {
        border-radius: 8px;
        font-weight: 500;
        border: 1px solid #e2e8f0;
        transition: all 0.2s ease-in-out;
    }

    /* Subtiele hover-effecten voor knoppen */
    div.stButton > button:hover {
        border-color: #ff4b4b;
        color: #ff4b4b;
    }

    /* Strakke schaduw en afgeronde hoeken voor elementen / containers */
    div[data-testid="stVerticalBlock"] > div[style*="border"] {
        border-radius: 10px;
        padding: 15px;
        background-color: #ffffff;
        box-shadow: 0 1px 3px rgba(0,0,0,0.05);
    }
    </style>
""", unsafe_allow_html=True)

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

st.title("Hardloop & Herstel Monitor")
st.markdown("Monitor je trainingsbelasting en voedingsherstel op basis van je Strava-activiteiten.")

# Vaste Client ID en Secret
DEFAULT_CLIENT_ID = 284865
DEFAULT_CLIENT_SECRET = "2812bd767959baabe261e8da78c2950565da4614"

# --- SESSION STATE INITIALISATIE ---
if "access_token" not in st.session_state: st.session_state.access_token = None
if "refresh_token" not in st.session_state: st.session_state.refresh_token = None
if "max_hr" not in st.session_state: st.session_state.max_hr = 190
if "rest_hr" not in st.session_state: st.session_state.rest_hr = 45
if "body_weight" not in st.session_state: st.session_state.body_weight = 65.0

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
    st.info("👋 Welkom! Log in met je Strava-account om je eigen hardloop- en fietsdata te analyseren.")

    redirect_uri = "https://test-project-esbc6cm8557nybkrc4o8kv.streamlit.app"
    authorize_url = client.authorization_url(
        client_id=DEFAULT_CLIENT_ID,
        redirect_uri=redirect_uri,
        scope=['read', 'activity:read_all']
    )

    st.link_button("🔗 Inloggen met Strava", authorize_url, use_container_width=True)

else:
    # --- ZIJBALK VOOR INSTELLINGEN & FILTERS ---
    st.sidebar.markdown("---")
    sport_filter = st.sidebar.selectbox(
        "🎯 Filter Activiteiten:",
        ["Alle activiteiten", "Hardloop activiteiten", "Fiets activiteiten"]
    )

    st.sidebar.markdown("### ⚙ Profiel & Instellingen")

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

        with st.spinner("Je Strava-activiteiten ophalen... 🏃‍♂🚴‍♂️"):
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
            act_type_str = str(getattr(act, 'type', ''))
            if act.type and ('Run' in act_type_str or 'Ride' in act_type_str or 'VirtualRide' in act_type_str):
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

                    is_ride = 'Ride' in act_type_str
                    cal_factor = 0.45 if is_ride else 1.03

                    if avg_hr > st.session_state.rest_hr and st.session_state.max_hr > st.session_state.rest_hr:
                        hr_reserve_ratio = (avg_hr - st.session_state.rest_hr) / (
                                    st.session_state.max_hr - st.session_state.rest_hr)
                        training_load = moving_time_mins * (hr_reserve_ratio * (1.2 if is_ride else 1.5))
                    else:
                        training_load = dist_km * (4 if is_ride else 10)

                    estimated_cals = st.session_state.body_weight * dist_km * cal_factor

                    parsed_activities.append({"datetime": act_date, "load": training_load})

                    act_name = getattr(act, 'name', 'Activiteit')
                    sport_emoji = "🚴‍♂️" if is_ride else "🏃‍♂️"

                    detailed_activities_list.append({
                        "id": act.id,
                        "datetime": act_date,
                        "type": "Fietsen" if is_ride else "Hardlopen",
                        "label": f"{sport_emoji} {act_date.strftime('%d-%m-%Y')} - {act_name} ({round(dist_km, 1)} km)",
                        "name": act_name,
                        "distance": round(dist_km, 2),
                        "time_mins": round(moving_time_mins, 1),
                        "calories": round(estimated_cals, 0),
                        "avg_hr": avg_hr,
                        "load": training_load,
                        "start_monday": (act_date - datetime.timedelta(days=act_date.weekday())).date()
                    })

        # --- STAP 3: PAS HET SPORTFILTER TOE VOORAF ---
        if sport_filter == "Hardloop activiteiten":
            filtered_activities_list = [act for act in detailed_activities_list if act["type"] == "Hardlopen"]
        elif sport_filter == "Fiets activiteiten":
            filtered_activities_list = [act for act in detailed_activities_list if act["type"] == "Fietsen"]
        else:
            filtered_activities_list = detailed_activities_list

        filtered_raw_weeks = {m_date: {"dist": 0.0, "load": 0.0, "hrs": [], "times": 0.0, "cals": 0.0} for m_date in weeks_list}
        for act in filtered_activities_list:
            act_monday = act["start_monday"]
            if act_monday in filtered_raw_weeks:
                if act["avg_hr"] > 0:
                    filtered_raw_weeks[act_monday]["hrs"].append(act["avg_hr"])
                filtered_raw_weeks[act_monday]["dist"] += act["distance"]
                filtered_raw_weeks[act_monday]["load"] += act["load"]
                filtered_raw_weeks[act_monday]["times"] += act["time_mins"]
                filtered_raw_weeks[act_monday]["cals"] += act["calories"]

        sorted_dates = sorted(filtered_raw_weeks.keys())
        weekly_loads = [round(filtered_raw_weeks[m]["load"], 1) for m in sorted_dates]

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
            d = filtered_raw_weeks[m]
            avg_h = sum(d["hrs"]) / len(d["hrs"]) if d["hrs"] else 0.0
            weekly_details.append({
                "Week Start": m.strftime("%d %b"),
                "Afstand (km)": round(d["dist"], 1),
                "Gem. HR": round(avg_h, 1) if avg_h > 0 else "N.B.",
                "Tijd (min)": round(d["times"], 1),
                "Kcal": round(d["cals"], 0),
                "Load": round(d["load"], 1)
            })

    except Exception as e:
        st.error(f"Er ging iets mis bij het ophalen van je Strava-activiteiten: {e}")
        filtered_activities_list = []
        weekly_details = []
        chart_df = pd.DataFrame(columns=["Datum", "Trainingsbelasting"])
        acute_load, chronic_load = 0.0, 1.0

    # --- TABS MAKEN VOOR NAVIGATIE ---
    tab_acwr, tab_nutrition, tab_fridge = st.tabs(["📊 Belasting", "🍎 Voeding & Herstel", "🧑‍🍳 Persoonlijke Chef (work in progress)"])

    with tab_acwr:
        acwr = acute_load / chronic_load if chronic_load > 0 else 0

        st.subheader("📊 Hoe intensief belast jij jezelf?")
        st.markdown(
            "Hier zie je in één oogopslag of je op een veilige manier opbouwt richting je doelen, of dat het risico op overbelasting toeneemt."
        )

        col1, col2, col3 = st.columns(3)
        col1.metric("Korte termijn (Afgelopen 7 dagen)", f"{round(acute_load, 1)}",
                    help="De totale trainingsbelasting die je de afgelopen week hebt verwerkt.")
        col2.metric("Langetermijn (Gemiddelde van 4 weken)", f"{round(chronic_load, 1)}",
                    help="Je fitheidsbasis: hoeveel belasting je lichaam de afgelopen maand gemiddeld gewend is te dragen.")
        col3.metric("Belastingsbalans (Ratio)", f"{round(acwr, 2)}",
                    help="Verhouding tussen je recente belasting en je basisfitheid.")

        if acwr < 0.8:
            st.info(
                "⚠️ **Ondertraining:** Je belasting is vrij laag vergeleken met je baseline. Je kunt de trainingen geleidelijk weer opschroeven.")
        elif 0.8 <= acwr <= 1.3:
            st.success(
                "🟢 **Optimaal:** Veilige opbouw, perfect voor progressie! Je zit in de 'sweet spot' om fitter te worden.")
        elif 1.3 < acwr <= 1.5:
            st.warning(
                "🟠 **Let op:** Snelle piek in belasting vergeleken met je basis. Bouw tijdelijk wat extra rust in.")
        else:
            st.error(
                "🔴 **Hoog risico:** Grote kans op overbelasting! Je vraagt opeens veel meer van je lichaam dan het gewend is.")

        # Koptekst + Info knop naast elkaar
        col_title, col_info = st.columns([6, 1])
        with col_title:
            st.subheader("📈 Wekelijkse Belasting")
        with col_info:
            with st.popover("ℹ️ Uitleg"):
                st.markdown("### Hoe wordt de belasting berekend?")
                st.markdown(
                    "De trainingsbelasting combineert de **duur** en **intensiteit** van al je trainingen:\n\n"
                    "- **Hartslagreserve:** Er wordt gekeken naar hoeveel tijd je boven je rusthartslag hebt getraind ten opzichte van je maximale hartslag.\n"
                    "- **Weging per sport:** Fietsen en hardlopen hebben een eigen vermenigvuldigingsfactor voor de impact op je lichaam.\n"
                    "- **Doel:** Dit helpt je om je Acute vs. Chronic workload (ACWR) in de gaten te houden zodat je niet overbelast raakt!"
                )

        fig = px.line(
            chart_df, x="Datum", y="Trainingsbelasting", markers=True,
            labels={"Datum": "Datum", "Trainingsbelasting": "Load"}
        )
        fig.update_layout(xaxis_type="date", margin=dict(l=10, r=10, t=10, b=10), height=300)
        st.plotly_chart(fig, use_container_width=True)

        fig = px.line(
            chart_df, x="Datum", y="Trainingsbelasting", markers=True,
            labels={"Datum": "Datum", "Trainingsbelasting": "Load"}
        )

        if weekly_details:
            st.subheader("📋 Historie per week")
            df_details = pd.DataFrame(weekly_details)
            st.dataframe(df_details.iloc[::-1], use_container_width=True, hide_index=True)

    with tab_nutrition:
        st.subheader("🍎 Uitgebreid Voeding- & Hersteladvies")
        st.markdown(
            "Selecteer een training om een nauwkeurige herstelanalyse, gerichte macro's en een uitgebreide variatie aan maaltijdrecepten te bekijken."
        )

        if filtered_activities_list:
            cutoff_7d = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=7)
            recent_acts = [act for act in filtered_activities_list if act["datetime"] >= cutoff_7d]

            if recent_acts:
                activity_labels = [act["label"] for act in recent_acts]
                chosen_label = st.selectbox("Kies een training (afgelopen 7 dagen):", activity_labels,
                                            key="nutrition_recent_select")
                selected_act = next(act for act in recent_acts if act["label"] == chosen_label)
            else:
                st.info("Geen activiteiten in de afgelopen 7 dagen. Hier is je meest recente training:")
                activity_labels = [act["label"] for act in filtered_activities_list[:5]]
                chosen_label = st.selectbox("Kies een training:", activity_labels, key="nutrition_older_select")
                selected_act = next(act for act in filtered_activities_list if act["label"] == chosen_label)

            st.markdown("---")
            col_n1, col_n2, col_n3 = st.columns(3)
            col_n1.metric("Afstand", f"{selected_act['distance']} km")
            col_n2.metric("Duur", f"{selected_act['time_mins']} min")
            col_n3.metric("Verbrande Kcal", f"{selected_act['calories']} kcal")

            cals = selected_act['calories']
            duration = selected_act['time_mins']
            name_lower = selected_act['name'].lower()
            cals_per_min = cals / duration if duration > 0 else 10

            # ---------------------------------------------------------
            # HIER START DE AANGEPASTE HERSTELBEREKENING
            # ---------------------------------------------------------
            if any(k in name_lower for k in
                   ["interval", "tempo", "VO2", "race", "wedstrijd", "sprint"]) or cals_per_min > 14:
                training_type = "Intensieve Interval- of Temposessie"
                recovery_hours = 36
                recovery_status = "⚡ Explosieve belasting — Goed herstel van glycogeen en spieren aanbevolen."
                meal_cat = "zwaar"
            elif duration > 90 or cals > 700:
                training_type = "Lange Duurloop (LSD)"
                recovery_hours = 40
                recovery_status = "🟠 Grote duurbelasting — Uitgebreid herstel van vocht en koolhydraten nodig."
                meal_cat = "zwaar"
            elif 450 <= cals <= 700 or 45 <= duration <= 90:
                training_type = "Solide Duurtraining"
                recovery_hours = 24
                recovery_status = "🟢 Prima training! Je herstelt hier heel vlot van met goede voeding."
                meal_cat = "middel"
            elif 200 <= cals or 25 <= duration < 45:
                training_type = "Lichte Duurloop / Vlot Rondje"
                recovery_hours = 16
                recovery_status = "🟢 Lekker soepel loopje — Je bent zo weer volledig hersteld!"
                meal_cat = "licht"
            else:
                training_type = "Kort Herstel / Uitlopen"
                recovery_hours = 12
                recovery_status = "🟢 Minimale belasting — Vrijwel direct weer fris."
                meal_cat = "licht"

            st.markdown("### ⏱ Genuanceerde Herstelanalyse")
            st.info(
                f"**Sectortype:** {training_type}\n\n**Advies:** {recovery_status} \n*Verwachte hersteltijd: **ca. {recovery_hours} uur**.*")

            carbs_target = int(cals * 0.55 / 4)
            protein_target = int(st.session_state.body_weight * 0.35)

            st.markdown("### 🎯 Doelstellingen voor deze sessie")
            col_m1, col_m2 = st.columns(2)
            col_m1.metric("Koolhydraten aanvullen", f"ca. {carbs_target} gram")
            col_m2.metric("Eiwitten (Spierherstel)", f"ca. {protein_target} gram")

            st.markdown("---")
            st.markdown("### 🍳 Uitgebreide Receptendatabase")

            # SLIMME RECEPTEN DATABASE
            recipe_database = {
                "zwaar": [
                    {
                        "title": "Power Haver-Kwark Bowl met Rood Fruit",
                        "kcal": 550, "carbs": 70, "protein": 35,
                        "ingredients": [
                            "70g havermout",
                            "200g magere kwark",
                            "1 banaan",
                            "Handje blauwe bessen",
                            "1 el chiazaad",
                            "Scheutje honing"
                        ],
                        "steps": [
                            "Meng de havermout met de kwark en een scheutje water of melk.",
                            "Snijd de banaan in plakjes en verdeel samen met het rode fruit, chiazaad en de honing over de bowl."
                        ]
                    },
                    {
                        "title": "Volkoren Wrap met Tonijn, Avocado & Bonen",
                        "kcal": 650, "carbs": 60, "protein": 40,
                        "ingredients": [
                            "2 volkoren wraps",
                            "1 blikje tonijn (op water)",
                            "1/2 avocado",
                            "50g kidneybonen",
                            "Sla en komkommer",
                            "Yoghurt-knoflookdressing"
                        ],
                        "steps": [
                            "Prak de avocado en meng met de uitgelekte tonijn en kidneybonen.",
                            "Leg sla op de wraps, verdeel het tonijnmengsel erover, voeg komkommer toe en rol strak op."
                        ]
                    },
                    {
                        "title": "Gezonde Pasta Bolognese met Rundergehakt & Champignons",
                        "kcal": 750, "carbs": 85, "protein": 45,
                        "ingredients": [
                            "90g volkoren spaghetti",
                            "130g mager rundergehakt",
                            "150g champignons",
                            "1 ui & 2 knoflookteentjes",
                            "200ml passata (gezeefde tomaten)",
                            "Italiaanse kruiden"
                        ],
                        "steps": [
                            "Kook de pasta volgens de aanwijzingen op de verpakking.",
                            "Fruit de ui en knoflook, bak het gehakt rul en bak de champignons mee.",
                            "Voeg de passata en kruiden toe, laat kort pruttelen en serveer over de pasta."
                        ]
                    },
                    {
                        "title": "Rijstwafels met Pindakaas & Banaan",
                        "kcal": 300, "carbs": 35, "protein": 10,
                        "ingredients": [
                            "4 rijstwafels",
                            "2 el 100% pindakaas",
                            "1 banaan in plakjes",
                            "Snufje kaneel"
                        ],
                        "steps": [
                            "Besmeer de rijstwafels rijkelijk met de pindakaas.",
                            "Leg de plakjes banaan erop en maak af met een snufje kaneel."
                        ]
                    }
                ],
                "middel": [
                    {
                        "title": "Proteïne Yoghurt met Cruesli & Appel",
                        "kcal": 420, "carbs": 50, "protein": 30,
                        "ingredients": [
                            "250ml Griekse yoghurt 0% of Skyr",
                            "40g volkoren granen / cruesli",
                            "1 appel in stukjes",
                            "Snufje kaneel"
                        ],
                        "steps": [
                            "Schep de Skyr in een mooie kom.",
                            "Voeg de knapperige granen toe, garneer met de stukjes appel en bestrooi met kaneel."
                        ]
                    },
                    {
                        "title": "Omelet Wrap met Kipfilet en Spinazie",
                        "kcal": 480, "carbs": 35, "protein": 38,
                        "ingredients": [
                            "2 eieren en een scheutje melk",
                            "Handje verse spinazie",
                            "70g kipfilet plakjes",
                            "1 volkoren wrap of boterham"
                        ],
                        "steps": [
                            "Klop de eieren los en bak een dunne omelet in de pan met de spinazie erdoor.",
                            "Leg de omelet op de wrap of serveer samen met de kipfilet."
                        ]
                    },
                    {
                        "title": "Wokschotel met Kip, Noedels & Oosterse Groenten",
                        "kcal": 580, "carbs": 65, "protein": 35,
                        "ingredients": [
                            "75g volkoren noedels of mie",
                            "120g kipfilet reepjes",
                            "200g wokgroenten",
                            "2 el sojasaus, gemberpoeder & 1 tl sesamolie"
                        ],
                        "steps": [
                            "Kook de noedels volgens de aanwijzingen.",
                            "Bak de kip in de wokpan en voeg de wokgroenten toe.",
                            "Voeg de noedels, sojasaus en sesamolie toe en wok het geheel nog 2 minuten door."
                        ]
                    }
                ],
                "licht": [
                    {
                        "title": "Lichte Smoothie van Rood Fruit & Kwark",
                        "kcal": 300, "carbs": 40, "protein": 22,
                        "ingredients": [
                            "150g diepvries rood fruit",
                            "150ml magere kwark",
                            "100ml water of amandelmelk"
                        ],
                        "steps": [
                            "Voeg alle ingrediënten toe aan een blender.",
                            "Blend tot een gladde, frisse en lichte herstelsmoothie."
                        ]
                    },
                    {
                        "title": "Volkoren Boterhammen met Hüttenkäse & Komkommer",
                        "kcal": 350, "carbs": 35, "protein": 25,
                        "ingredients": [
                            "3 volkoren boterhammen",
                            "100g hüttenkäse",
                            "Halve komkommer in plakjes",
                            "Peper en zout naar smaak"
                        ],
                        "steps": [
                            "Besmeer de sneetjes brood met een royale laag hüttenkäse.",
                            "Beleg met de plakjes komkommer en breng op smaak met peper en zout."
                        ]
                    },
                    {
                        "title": "Frisse Salade met Quinoa, Feta & Kikkererwten",
                        "kcal": 450, "carbs": 50, "protein": 20,
                        "ingredients": [
                            "65g gekookte quinoa",
                            "100g kikkererwten (uit blik)",
                            "40g feta (light)",
                            "Cherrytomaatjes, komkommer en dressing van olijfolie/citroen"
                        ],
                        "steps": [
                            "Meng de gekookte quinoa met de uitgespoelde kikkererwten en verse groenten.",
                            "Verkruimel de feta erboven en besprenkel met de frisse dressing."
                        ]
                    }
                ]
            }

            # Automatisch de recepten inladen en netjes onder elkaar tonen
            available_recipes = recipe_database.get(meal_cat, recipe_database["middel"])

            for recipe in available_recipes:
                with st.expander(f"🍽️ {recipe['title']} (ca. {recipe['kcal']} kcal)"):
                    st.markdown(
                        f"**Energie:** ca. **{recipe['kcal']} kcal** | Koolhydraten: ~{recipe['carbs']}g | Eiwitten: ~{recipe['protein']}g")

                    st.markdown("**Ingrediënten:**")
                    for ing in recipe['ingredients']:
                        st.markdown(f"- {ing}")

                    st.markdown("**Bereidingswijze:**")
                    for s_idx, step in enumerate(recipe['steps'], 1):
                        st.markdown(f"{s_idx}. {step}")
        else:
            st.warning("Geen activiteiten gevonden om voedingsadvies voor te genereren.")
    with tab_fridge:
        st.subheader("🧑‍🍳 Persoonlijke Chef — Kook op basis van je training & voorraad")
        st.markdown(
            "De AI kijkt naar de training die je hebt geselecteerd in het voedingstabblad en bedenkt een recept dat exact past bij jouw herstelbehoefte van die dag!")

        if 'selected_act' in locals() and selected_act:
            train_name = selected_act['name']
            train_type_str = selected_act['type']
            target_cals_fridge = int(selected_act['calories'])
            train_dist = selected_act['distance']

            target_carbs_fridge = int(target_cals_fridge * 0.6 / 4)
            target_protein_fridge = int(st.session_state.body_weight * 0.3)

            st.success(
                f"📌 **Gekoppelde training:** {train_type_str} — *{train_name}* ({train_dist} km | **{target_cals_fridge} kcal**)")

            col_f1, col_f2 = st.columns(2)
            col_f1.metric("Doel Energie", f"{target_cals_fridge} kcal")
            col_f2.metric("Doel Eiwit / Koolh.", f"{target_protein_fridge}g E / {target_carbs_fridge}g K")

        elif filtered_activities_list:
            latest_act = filtered_activities_list[0]
            target_cals_fridge = int(latest_act['calories'])
            target_carbs_fridge = int(target_cals_fridge * 0.6 / 4)
            target_protein_fridge = int(st.session_state.body_weight * 0.3)

            st.info(
                f"💡 Geen actieve selectie gevonden; we gebruiken je meest recente activiteit: **{latest_act['name']} ({target_cals_fridge} kcal)**")
        else:
            target_cals_fridge = 650
            target_carbs_fridge = int(target_cals_fridge * 0.6 / 4)
            target_protein_fridge = int(st.session_state.body_weight * 0.3)
            st.warning("⚠️ Geen activiteiten gevonden. Standaard hersteldoel van 650 kcal wordt gebruikt.")

        st.markdown("---")

        input_methode = st.radio(
            "Kies invoermethode voor je foto:",
            ["Bestand / Fotobibliotheek uploaden", "Direct foto maken met camera"],
            horizontal=True,
            key="input_methode_crop"
        )

        uploaded_image = None

        if input_methode == "Bestand / Fotobibliotheek uploaden":
            uploaded_image = st.file_uploader("Kies een foto uit je bestanden of foto's:", type=["jpg", "jpeg", "png"],
                                              key="fridge_file_uploader")
        else:
            uploaded_image = st.camera_input("Maak een foto van je koelkast / ingrediënten:", key="fridge_camera_input")

        if uploaded_image is not None:
            selected_aspect = None

            st.info(
                "✂️ Sleep en pas het kader hieronder aan om de foto bij te snijden op de ingrediënten die je wilt gebruiken.")

            cropped_img = st_cropper(
                Image.open(uploaded_image),
                realtime_update=True,
                aspect_ratio=selected_aspect,
                key="fridge_image_cropper"
            )

            st.markdown("---")
            st.write("Jouw geselecteerde uitsnede:")
            st.image(cropped_img, caption="Bijgesneden ingrediënten", width=400)

            if st.button("🍳 Genereer Recept voor deze training", key="generate_recipe_btn"):
                with st.spinner(
                        "De AI analyseert je bijgesneden foto en stemt het recept af op je trainingsherstel..."):
                    try:
                        from google import genai
                        import time

                        api_key = st.secrets["GEMINI_API_KEY"]
                        client = genai.Client(api_key=api_key)

                        prompt = f"""
                                    Je bent een professionele sportdiëtist en chef-kok voor duursporters. De gebruiker heeft zojuist een foto gestuurd van de inhoud van zijn koelkast/voorraadkast.
                                    Bekijk de foto goed en identificeer welke bruikbare ingrediënten hierop te zien zijn.

                                    De gebruiker heeft zojuist een training voltooid en heeft exact de volgende voedingsdoelen nodig voor herstel:
                                    - Totaal energie: ca. {target_cals_fridge} kcal
                                    - Koolhydraten: ca. {target_carbs_fridge} gram
                                    - Eiwitten: ca. {target_protein_fridge} gram

                                    Bedenk een lekker, praktisch herstelrecept dat *alleen* (of voornamelijk) gebruikmaakt van de ingrediënten die je op de foto ziet.

                                    Geef in je antwoord:
                                    1. **Een lijst van gedetecteerde ingrediënten** van de foto die je gebruikt.
                                    2. **De naam van het recept**.
                                    3. **De geschatte macro's en calorieën** (zorg dat deze dicht bij de doelen van {target_cals_fridge} kcal liggen).
                                    4. **Een duidelijke bereidingswijze** in stappen.
                                    """

                        max_retries = 3
                        response = None
                        for attempt in range(max_retries):
                            try:
                                response = client.models.generate_content(
                                    model='gemini-3.8-flash',
                                    contents=[cropped_img, prompt]
                                )
                                break
                            except Exception as api_err:
                                err_str = str(api_err)
                                if "503" in err_str and attempt < max_retries - 1:
                                    time.sleep((attempt + 1) * 3)
                                    continue
                                else:
                                    raise api_err

                        st.markdown("---")
                        st.markdown("### 🧑‍🍳 Jouw AI Herstelrecept op maat:")
                        st.markdown(response.text)

                    except Exception as e:
                        st.error(f"Er ging iets mis bij het analyseren van de foto: {e}")
        else:
            st.info("Upload hierboven een foto of maak een foto met je camera om te beginnen.")