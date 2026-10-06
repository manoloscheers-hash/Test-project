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

                # --- 3. VARIËRENDE & GESCHAALDE VOORBEELDMAALTIJDEN ---
                # We gebruiken de ID of unieke eigenschappen van de activiteit om te zorgen dat je niet steeds dezelfde maaltijden krijgt.

                # Bepaal een variatie-index op basis van de activiteit ID of afstand
                act_hash = hash(str(selected_act['id'])) % 3  # Geeft 0, 1 of 2 als unieke variant

                if training_type == "Intensief (Interval / Tempo)":
                    c_m1 = int(cals * 0.35)
                    c_m2 = int(cals * 0.65)

                    if act_hash == 0:
                        st.markdown(f"""
                                        *Intensieve sessie ({cals} kcal) — Variatie A (Snel & Koolhydrietenrijk)*

                                        **1. Witte Rijst met Kipfilet & Zoete Saus**
                                        * **Energie:** ca. **{c_m1} kcal** | Koolhydraten: ~{int(c_m1 * 0.70 / 4)}g | Eiwitten: ~{int(c_m1 * 0.20 / 4)}g
                                        * *Wat:* 90g witte rijst, 120g gebakken kipfilet en een lichte zoete chilisaus.
                                        * *Waarom:* Razendsnelle opname van glycogeen door de witte rijst.

                                        **2. Hartige Power Wraps**
                                        * **Energie:** ca. **{c_m2} kcal** | Koolhydraten: ~{int(c_m2 * 0.55 / 4)}g | Eiwitten: ~{int(c_m2 * 0.30 / 4)}g
                                        * *Wat:* 2 grote volkoren wraps gevuld met tonijn (of vega-reepjes), mais, kidneybonen en guacamole.
                                        * *Waarom:* Optimale mix van complexe koolhydraten en eiwitten voor spierherstel.
                                        """)
                    elif act_hash == 1:
                        st.markdown(f"""
                                        *Intensieve sessie ({cals} kcal) — Variatie B (De Smoothie & Pasta-combinatie)*

                                        **1. Herstel-Smoothiekom met Granola**
                                        * **Energie:** ca. **{c_m1} kcal** | Koolhydraten: ~{int(c_m1 * 0.65 / 4)}g | Eiwitten: ~{int(c_m1 * 0.25 / 4)}g
                                        * *Wat:* Kom van 250g magere kwark, 1 banaan, hand bosbessen en 40g granola on top.
                                        * *Waarom:* Snel en fris na een pittige inspanning.

                                        **2. Volkoren Spaghetti Bolognese**
                                        * **Energie:** ca. **{c_m2} kcal** | Koolhydraten: ~{int(c_m2 * 0.60 / 4)}g | Eiwitten: ~{int(c_m2 * 0.25 / 4)}g
                                        * *Wat:* 100g volkoren spaghetti met mager rundergehakt (of linzen) en tomaten-groentensaus.
                                        * *Waarom:* Klassieke brandstof om je glycogeenvoorraad maximaal mee aan te vullen.
                                        """)
                    else:
                        st.markdown(f"""
                                        *Intensieve sessie ({cals} kcal) — Variatie C (Pannenkoeken & Omelet)*

                                        **1. Banaan-Haver Pannenkoeken**
                                        * **Energie:** ca. **{c_m1} kcal** | Koolhydraten: ~{int(c_m1 * 0.65 / 4)}g | Eiwitten: ~{int(c_m1 * 0.20 / 4)}g
                                        * *Wat:* 3 pannenkoeken gemaakt van 1 geprakte banaan, 1 ei en 60g havermeel, afgetopt met honing.
                                        * *Waarom:* Natuurlijke suikers en trage koolhydraten gecombineerd.

                                        **2. Noedels met Tofu/Kip & Groenten-wok**
                                        * **Energie:** ca. **{c_m2} kcal** | Koolhydraten: ~{int(c_m2 * 0.60 / 4)}g | Eiwitten: ~{int(c_m2 * 0.25 / 4)}g
                                        * *Wat:* Noedels gewokt met een ruime portie groenten, cashewnoten en kipreepjes/tofu.
                                        * *Waarom:* Snelle koolhydraten uit noedels en gezonde vetten/eiwitten.
                                        """)

                elif training_type == "Lange Duurloop (LSD)":
                    c_m1 = int(cals * 0.35)
                    c_m2 = int(cals * 0.65)

                    if act_hash == 0:
                        st.markdown(f"""
                                        *Lange Duurloop ({cals} kcal) — Variatie A (Oats & Volkoren)*

                                        **1. Kaneel-Appel Havermout**
                                        * **Energie:** ca. **{c_m1} kcal** | Koolhydraten: ~{int(c_m1 * 0.65 / 4)}g | Eiwitten: ~{int(c_m1 * 0.20 / 4)}g
                                        * *Wat:* 70g havermout in melk met een appel, handje rozijnen en een lepel pindakaas.
                                        * *Waarom:* Ideaal na een lange duurloop voor geleidelijke energieafgifte.

                                        **2. Quinoa-Bowl met Geroosterde Groenten & Zalm/Kip**
                                        * **Energie:** ca. **{c_m2} kcal** | Koolhydraten: ~{int(c_m2 * 0.55 / 4)}g | Eiwitten: ~{int(c_m2 * 0.30 / 4)}g
                                        * *Wat:* Kom quinoa met geroosterde pompoen/wortel, feta en kipfilet of zalm.
                                        * *Waarom:* Rijk aan trage koolhydraten en gezonde omega-3 vetzuren.
                                        """)
                    elif act_hash == 1:
                        st.markdown(f"""
                                        *Lange Duurloop ({cals} kcal) — Variatie B (Brood & Couscous)*

                                        **1. Geroosterde Volkoren Boterhammen met Avocado & Eieren**
                                        * **Energie:** ca. **{c_m1} kcal** | Koolhydraten: ~{int(c_m1 * 0.45 / 4)}g | Eiwitten: ~{int(c_m1 * 0.25 / 4)}g
                                        * *Wat:* 3 sneetjes volkoren brood, 1 geprakte avocado, 2 gekookte eieren en zeezout.
                                        * *Waarom:* Vult direct je zouten (natrium) aan na lang zweten.

                                        **2. Couscous Schotel met Kikkererwten & Feta**
                                        * **Energie:** ca. **{c_m2} kcal** | Koolhydraten: ~{int(c_m2 * 0.60 / 4)}g | Eiwitten: ~{int(c_m2 * 0.25 / 4)}g
                                        * *Wat:* Couscous met kikkererwten, komkommer, tomaat, olijfolie en fetablokjes.
                                        * *Waarom:* Licht verteerbare koolhydraten die snel energie geven na kilometers maken.
                                        """)
                    else:
                        st.markdown(f"""
                                        *Lange Duurloop ({cals} kcal) — Variatie C (Aardappel & Griesmeel)*

                                        **1. Gebakken Aardappelpartjes met Kwark-dip**
                                        * **Energie:** ca. **{c_m1} kcal** | Koolhydraten: ~{int(c_m1 * 0.60 / 4)}g | Eiwitten: ~{int(c_m1 * 0.25 / 4)}g
                                        * *Wat:* In de oven geroosterde aardappels met een frisse kruidenkwark dip.
                                        * *Waarom:* Aardappelen zijn een fantastische bron van kalium en koolhydraten voor lopers.

                                        **2. Volkoren Aardappel-Prei Stamppot (of Rijstschotel)**
                                        * **Energie:** ca. **{c_m2} kcal** | Koolhydraten: ~{int(c_m2 * 0.55 / 4)}g | Eiwitten: ~{int(c_m2 * 0.30 / 4)}g
                                        * *Wat:* Stamppot of ovenschotel met mager gehakt of vegetarische rookworst.
                                        * *Waarom:* Traditioneel en vullend om je energiereserves weer volledig op te laden.
                                        """)
                else:
                    c_m1 = int(max(cals, 350) * 0.50)
                    c_m2 = int(max(cals, 350) * 0.50)

                    if act_hash == 0:
                        st.markdown(f"""
                                        *Herstelloop ({cals} kcal) — Variatie A*

                                        **1. Magere Kwark met Blauwe Bessen & Walnoten**
                                        * **Energie:** ca. **{c_m1} kcal** | Koolhydraten: ~{int(c_m1 * 0.40 / 4)}g | Eiwitten: ~{int(c_m1 * 0.45 / 4)}g
                                        * *Wat:* 250g kwark met handje bessen en walnoten.
                                        """)
                    elif act_hash == 1:
                        st.markdown(f"""
                                        *Herstelloop ({cals} kcal) — Variatie B*

                                        **1. Smoothie van Bosvruchten & Eiwitpoeder**
                                        * **Energie:** ca. **{c_m1} kcal** | Koolhydraten: ~{int(c_m1 * 0.50 / 4)}g | Eiwitten: ~{int(c_m1 * 0.35 / 4)}g
                                        * *Wat:* Bevroren bosvruchten, magere melk en schep wei-eiwit.
                                        """)
                    else:
                        st.markdown(f"""
                                        *Herstelloop ({cals} kcal) — Variatie C*

                                        **1. Griekse Yoghurt met Honing & Amandelen**
                                        * **Energie:** ca. **{c_m1} kcal** | Koolhydraten: ~{int(c_m1 * 0.45 / 4)}g | Eiwitten: ~{int(c_m1 * 0.35 / 4)}g
                                        * *Wat:* Kom Griekse yoghurt met scheutje honing en gehakte amandelen.
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