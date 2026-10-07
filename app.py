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


# ==============================================================================
# MODULE: ACTIONABLE COACHING & DOELGERICHTE PERIODISERING
# ==============================================================================

def render_actionable_coaching_module(acwr_value, acute_load, chronic_load, card_bg, card_border, text_main, text_sub,
                                      user_goal):
    """
    Genereert helder, direct toepasbaar trainingsadvies op basis van de ACWR
    en past zich volledig aan op het gekozen doel (bijv. 5km, marathon, of vrij).
    """
    st.subheader("🎯 Coach Advies & Doelmonitor")

    # Bepaal het advies op basis van de ACWR waarde en het gekozen doel
    is_vrij_trainen = ("vrij" in user_goal.lower()) or ("geen vast schema" in user_goal.lower())

    if is_vrij_trainen:
        if acwr_value < 0.8:
            status_color = "#3b82f6"
            status_title = "Luister naar je lichaam: Ruimte voor power"
            advice = "Je belasting is laag. Je voelt je waarschijnlijk fris en fit genoeg om lekker door te trekken als je daar zin in hebt."
            action = "👉 **Advies voor vandaag:** Heb je energie? Pak een mooie intensieve prikkel mee op gevoel!"
        elif 0.8 <= acwr_value <= 1.3:
            status_color = "#10b981"
            status_title = "Lekker in de flow"
            advice = "Je zit in een stabiele, fijne balans. Je conditie houdt zichzelf keurig op peil."
            action = "👉 **Advies voor vandaag:** Blijf lekker lopen op het ritme dat goed voelt."
        else:
            status_color = "#f59e0b"
            status_title = "Tijd voor wat extra rust"
            advice = "Je opgebouwde belasting is vrij hoog vergeleken met je recente baseline. Je merkt misschien dat je benen wat zwaarder aanvoelen."
            action = "👉 **Advies voor vandaag:** Las gerust een extra rustdag of een heel rustig herstelrondje in."
    else:
        if acwr_value < 0.8:
            status_color = "#3b82f6"
            status_title = "Groen Licht: Ruimte voor intensiteit"
            advice = f"Je belasting is momenteel aan de lage kant voor je doel ({user_goal}). Ruimte voor een gerichte prikkel."
            action = "👉 **Advies voor vandaag:** Voeg een kwalitatieve interval- of temposessie toe."
        elif 0.8 <= acwr_value <= 1.3:
            status_color = "#10b981"
            status_title = "Sweet Spot: Perfecte balans"
            advice = f"Je zit in de ideale opbouwzone richting je doel: {user_goal}."
            action = "👉 **Advies voor vandaag:** Houd je strak aan je opbouwende trainingsschema."
        elif 1.3 < acwr_value <= 1.5:
            status_color = "#f59e0b"
            status_title = "Waarschuwing: Snelle stijging"
            advice = "Je belasting stijgt sneller dan je fitheidsbasis kan bijbenen."
            action = "👉 **Advies voor vandaag:** Overweeg een rustdag om overbelasting te voorkomen."
        else:
            status_color = "#ef4444"
            status_title = "Gevaarlijke Piek: Gas terugnemen!"
            advice = "Alarmfase! Je ACWR is te hoog voor een veilig verloop van je schema."
            action = "👉 **Advies voor vandaag:** Neem direct rust of doe uitsluitend actieve hersteltraining."

    # Render de UI kaart voor de gebruiker
    st.markdown(f"""
        <div style="background: {card_bg}; border: {card_border}; border-left: 6px solid {status_color}; border-radius: 8px; padding: 16px; margin-bottom: 16px;">
            <h4 style="margin: 0 0 8px 0; color: {text_main};">{status_title}</h4>
            <p style="margin: 0 0 12px 0; font-size: 14px; color: {text_sub};">{advice}</p>
            <div style="background: rgba(255,255,255,0.03); padding: 10px; border-radius: 6px; font-weight: 600; color: {text_main};">
                {action}
            </div>
        </div>
    """, unsafe_allow_html=True)

    # --- DOELGERICHTE CHECK (Op 0 decimalen) ---
    with st.expander(f"🏁 Voortgang richting doel: {user_goal}"):
        if "Sub-2:40" in user_goal:
            st.markdown(f"""
                * **Streefpace:** ~3:47 min/km
                * **Huidige Acute Belasting:** {int(round(acute_load, 0))}
                * **Fitheidsbasis (Chronic Load):** {int(round(chronic_load, 0))}
            """)
            if chronic_load >= 500:
                st.success("✅ Je fitheidsbasis is solide genoeg om dit volume vast te houden voor een snelle marathon.")
            else:
                st.warning(
                    "⚠️ Je fitheidsbasis is nog wat aan de lage kant voor een sub-2:40 poging. Bouw gestaag uit.")
        elif "5 km" in user_goal or "10 km" in user_goal:
            st.markdown(f"""
                * **Focus:** Snelheid, VO2max en drempelwerk
                * **Huidige Acute Belasting:** {int(round(acute_load, 0))}
                * **Fitheidsbasis (Chronic Load):** {int(round(chronic_load, 0))}
            """)
            st.info("💡 Korte, intensieve prikkels en voldoende herstel zijn cruciaal voor een scherpe 5k/10k tijd.")
        elif "Halve Marathon" in user_goal:
            st.markdown(f"""
                * **Focus:** Drempelduurvermogen en tempo-uithoudingsvermogen
                * **Huidige Acute Belasting:** {int(round(acute_load, 0))}
                * **Fitheidsbasis (Chronic Load):** {int(round(chronic_load, 0))}
            """)
            st.info(
                "💡 Zorg voor een gezonde balans tussen langere duurlopen en blokkentraining op halve marathon tempo.")
        else:
            st.markdown(f"""
                * **Focus:** Vrij en flexibel trainen op gevoel
                * **Huidige Acute Belasting:** {int(round(acute_load, 0))}
                * **Fitheidsbasis (Chronic Load):** {int(round(chronic_load, 0))}
            """)
            st.success(
                "👍 Je traint zonder strak schema; gebruik deze cijfers puur als indicatie voor je herstel en energie.")


# --- HELPERS VOOR VERMOEIDHEIDSBEREKENING ---
def bereken_hr_load(zones_tijden):
    weegfactoren = [1.0, 2.0, 3.0, 4.5, 7.0]
    return sum(t * w for t, w in zip(zones_tijden, weegfactoren))


def bereken_session_score(activity, zones_tijden=None):
    if not zones_tijden:
        duur = activity.get('time_mins', 30)
        zones_tijden = [duur * 0.6, duur * 0.25, duur * 0.1, duur * 0.05, 0.0]

    hr_load = bereken_hr_load(zones_tijden)
    sport_type = activity.get('type', 'Hardlopen').lower()

    if 'swim' in sport_type or 'zwemmen' in sport_type:
        f_type = 0.8
    elif 'ride' in sport_type or 'cycle' in sport_type or 'fietsen' in sport_type:
        f_type = 1.0
    elif 'trail' in sport_type:
        f_type = 1.4
    else:
        f_type = 1.3

    d_plus = activity.get('elevation_gain', 0)
    d_min = activity.get('elevation_loss', 0)
    f_elev = 1 + (d_plus / 100 * 0.02) + (d_min / 100 * 0.03)
    f_cad = 1.0

    session_score = hr_load * f_type * f_elev * f_cad
    return round(session_score, 0)


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

    st.sidebar.markdown("### 🏆 Trainingsdoel Instellen")
    user_goal = st.sidebar.selectbox(
        "Kies of stel je doel in:",
        [
            "Sub-2:40 Marathon",
            "Halve Marathon Persoonlijk Record",
            "10 km Persoonlijk Record",
            "5 km Persoonlijk Record",
            "Geen vast schema (Train op gevoel)",
            "Algemene Conditie & Fitheid"
        ]
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
                    estimated_cals = st.session_state.body_weight * dist_km * cal_factor

                    elevation_gain = float(getattr(act, 'total_elevation_gain', 0.0) or 0.0)
                    elevation_loss = float(getattr(act, 'elevation_loss', 0.0) or 0.0)

                    temp_act_dict = {
                        'type': "Fietsen" if is_ride else "Hardlopen",
                        'time_mins': moving_time_mins,
                        'elevation_gain': elevation_gain,
                        'elevation_loss': elevation_loss
                    }

                    training_load = bereken_session_score(temp_act_dict)

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

        # --- SPORTFILTER TOEPASSEN ---
        if sport_filter == "Hardloop activiteiten":
            filtered_activities_list = [act for act in detailed_activities_list if act["type"] == "Hardlopen"]
        elif sport_filter == "Fiets activiteiten":
            filtered_activities_list = [act for act in detailed_activities_list if act["type"] == "Fietsen"]
        else:
            filtered_activities_list = detailed_activities_list

        filtered_raw_weeks = {m_date: {"dist": 0.0, "load": 0.0, "hrs": [], "times": 0.0, "cals": 0.0} for m_date in
                              weeks_list}
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
        weekly_loads = [int(round(filtered_raw_weeks[m]["load"], 0)) for m in sorted_dates]

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
                "Gem. HR": int(round(avg_h, 0)) if avg_h > 0 else "N.B.",
                "Tijd (min)": int(round(d["times"], 0)),
                "Kcal": int(round(d["cals"], 0)),
                "Load": int(round(d["load"], 0))
            })

    except Exception as e:
        st.error(f"Er ging iets mis bij het ophalen van je Strava-activiteiten: {e}")
        filtered_activities_list = []
        weekly_details = []
        chart_df = pd.DataFrame(columns=["Datum", "Trainingsbelasting"])
        acute_load, chronic_load = 0.0, 1.0

    # --- TABS MAKEN VOOR NAVIGATIE ---
    tab_acwr, tab_schema, tab_nutrition, tab_fridge = st.tabs(
        ["📊 Belasting", "📅 Trainingsschema", "🍎 Voeding & Herstel", "🧑‍🍳 Persoonlijke Chef (work in progress)"])
    with tab_acwr:
        acwr = acute_load / chronic_load if chronic_load > 0 else 0

        # --- STATUS WIDGET ---
        if acwr < 0.8:
            status_title = "Onderbelast (Opbouwfase)"
            status_color = "#3b82f6"
            status_bg = "linear-gradient(135deg, #1e3a8a 0%, #1e293b 100%)"
            status_desc = "Je zit onder je baseline. Ruimte om gecontroleerd te versnellen!"
        elif 0.8 <= acwr <= 1.3:
            status_title = "Productief / Sweet Spot"
            status_color = "#10b981"
            status_bg = "linear-gradient(135deg, #064e3b 0%, #0f172a 100%)"
            status_desc = "Optimale balans! Je bouwt maximale conditie op zonder overbelasting."
        elif 1.3 < acwr <= 1.5:
            status_title = "Piek / Vermoeidheid"
            status_color = "#f59e0b"
            status_bg = "linear-gradient(135deg, #78350f 0%, #0f172a 100%)"
            status_desc = "Hoge belasting. Zorg voor voldoende herstel de komende dagen."
        else:
            status_title = "Risico op Overbelasting"
            status_color = "#ef4444"
            status_bg = "linear-gradient(135deg, #7f1d1d 0%, #0f172a 100%)"
            status_desc = "Pas op! Je riskeert blessures. Las direct een rustperiode in."

        st.markdown(f"""
            <div style="background: {status_bg}; border: 1px solid rgba(255,255,255,0.1); padding: 20px; border-radius: 16px; margin-bottom: 20px; color: white; box-shadow: 0 10px 15px -3px rgba(0,0,0,0.3);">
                <div style="display: flex; justify-content: space-between; align-items: center;">
                    <span style="font-size: 12px; text-transform: uppercase; letter-spacing: 1.5px; color: #94a3b8; font-weight: 700;">Trainingsstatus</span>
                    <span style="background-color: {status_color}; color: white; padding: 4px 10px; border-radius: 20px; font-size: 11px; font-weight: bold;">LIVE</span>
                </div>
                <h2 style="margin: 8px 0 4px 0; color: #ffffff; font-size: 22px; font-weight: 700;">{status_title}</h2>
                <p style="margin: 0; font-size: 14px; color: #cbd5e1;">{status_desc}</p>
            </div>
        """, unsafe_allow_html=True)

        # --- VASTE DONKERE SPORT-WIDGETS (OP 0 DECIMALEN) ---
        card_bg = "#0f172a"
        card_border = "1px solid rgba(255, 255, 255, 0.1)"
        text_main = "#ffffff"
        text_sub = "#94a3b8"

        col1, col2, col3 = st.columns(3)

        with col1:
            st.markdown(f"""
                <div style="background: {card_bg}; border: {card_border}; padding: 16px; border-radius: 12px; text-align: center; margin-bottom: 8px; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.2);">
                    <div style="font-size: 11px; color: {text_sub}; font-weight: 700; text-transform: uppercase; letter-spacing: 0.5px;">🔥 Acute Load</div>
                    <div style="font-size: 26px; font-weight: 800; color: {text_main}; margin: 6px 0;">{int(round(acute_load, 0))}</div>
                    <div style="font-size: 11px; color: {text_sub};">Afgelopen 7 dagen</div>
                </div>
            """, unsafe_allow_html=True)

        with col2:
            st.markdown(f"""
                <div style="background: {card_bg}; border: {card_border}; padding: 16px; border-radius: 12px; text-align: center; margin-bottom: 8px; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.2);">
                    <div style="font-size: 11px; color: {text_sub}; font-weight: 700; text-transform: uppercase; letter-spacing: 0.5px;">🛡️ Chronic Load</div>
                    <div style="font-size: 26px; font-weight: 800; color: {text_main}; margin: 6px 0;">{int(round(chronic_load, 0))}</div>
                    <div style="font-size: 11px; color: {text_sub};">Fitheidsbasis (42d)</div>
                </div>
            """, unsafe_allow_html=True)

        with col3:
            st.markdown(f"""
                <div style="background: {card_bg}; border: {card_border}; padding: 16px; border-radius: 12px; text-align: center; margin-bottom: 8px; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.2);">
                    <div style="font-size: 11px; color: {text_sub}; font-weight: 700; text-transform: uppercase; letter-spacing: 0.5px;">⚖️ ACWR Ratio</div>
                    <div style="font-size: 26px; font-weight: 800; color: {status_color}; margin: 6px 0;">{round(acwr, 1)}</div>
                    <div style="font-size: 11px; color: {text_sub};">Doel: 0.8 - 1.3</div>
                </div>
            """, unsafe_allow_html=True)

        st.markdown("<br>", unsafe_allow_html=True)

        # --- AANROEP ACTIONABLE COACHING & DOELMODULE ---
        render_actionable_coaching_module(acwr, acute_load, chronic_load, card_bg, card_border, text_main, text_sub,
                                          user_goal)


        def render_training_schedule_module(user_goal):
            """
            Toont een basis weekprogramma op basis van het geselecteerde doel.
            """
            st.subheader(f"📅 Voorbeeld Trainingsschema: {user_goal}")
            st.markdown(
                "Heb je nog geen vast schema? Gebruik deze richtlijn als weekstructuur op basis van je gekozen doel:")

            if "5 km" in user_goal:
                st.markdown("""
                * **Dinsdag (Interval):** 6x 400m op 5k-tempo (met 90 sec wandel/drafpauze)
                * **Donderdag (Tempoloop):** 15 min inlopen, 15 min op drempeltempo (vlot maar gecontroleerd), 10 min uitlopen
                * **Zaterdag (Herstelloop):** 30 min heel rustig (Zone 1/2)
                * **Zondag (Duurloop):** 45-60 min ontspannen duurloop
                """)
            elif "10 km" in user_goal:
                st.markdown("""
                * **Dinsdag (Interval):** 5x 1000m op 10k-tempo (2 min wandel/drafpauze)
                * **Donderdag (Tempoloop):** 15 min inlopen, 20 min vlot duurtempo, 10 min uitlopen
                * **Zaterdag (Herstelloop):** 35 min rustig
                * **Zondag (Lange Duurloop):** 60-75 min gestaag duurtempo
                """)
            elif "Halve Marathon" in user_goal:
                st.markdown("""
                * **Dinsdag (Interval/Blokken):** 3x 2000m op Halve Marathon tempo (3 min pauze)
                * **Donderdag (Tempoloop):** 30 min vlot op race-tempo
                * **Zaterdag (Herstelloop):** 40 min rustige duurloop
                * **Zondag (Lange Duurloop):** 12 tot 16 km rustig opbouwend
                """)
            elif "Marathon" in user_goal:
                st.markdown("""
                * **Dinsdag (Interval/Drempel):** 4x 3000m op Marathon/Halve Marathon tempo (1 km herstel)
                * **Woensdag (Herstelloop):** 45-50 min rustig
                * **Donderdag (Marathon Tempo):** 10-14 km op beoogd marathontempo
                * **Zaterdag (Herstelloop):** 40 min heel rustig
                * **Zondag (Lange Duurloop):** 22 tot 30 km (stabiel Zone 2 / rustig)
                """)
            else:
                st.markdown("""
                * **Dinsdag:** 30-40 min vlot / wisselduurloop op gevoel
                * **Donderdag:** 30-45 min rustige duurloop
                * **Zondag:** 50-60 min ontspannen lange duurloop
                """)

        st.markdown("<br>", unsafe_allow_html=True)

        # --- GRAFIEK ---
        if "Chronic_Load" not in chart_df.columns:
            chart_df["Chronic_Load"] = chart_df["Trainingsbelasting"].rolling(window=4, min_periods=1).mean()

        chart_df["Sweet_Low"] = chart_df["Chronic_Load"] * 0.8
        chart_df["Sweet_High"] = chart_df["Chronic_Load"] * 1.3

        col_title, col_info = st.columns([6, 1])
        with col_title:
            st.subheader("📈 Trainingsbelasting")
        with col_info:
            with st.popover("ℹ️ Uitleg"):
                st.markdown("### Hoe wordt dit berekend?")
                st.markdown("""
                * **Acute Load (7 dagen):** Jouw trainingsbelasting van de afgelopen week.
                * **Chronic Load (42 dagen):** Je langetermijnfitheid (belastbaarheid).
                * **ACWR:** De verhouding tussen Acute en Chronische load. 
                * **Optimal Sweet Spot:** De groene band beweegt mee met je fitheid voor veilige progressie.
                """)

        fig = px.line(chart_df, x="Datum", y="Trainingsbelasting")

        fig.add_scatter(
            x=chart_df["Datum"], y=chart_df["Sweet_High"],
            mode='lines', line=dict(width=0), showlegend=False, hoverinfo='skip'
        )
        fig.add_scatter(
            x=chart_df["Datum"], y=chart_df["Sweet_Low"],
            mode='lines', line=dict(width=0), fill='tonexty',
            fillcolor='rgba(16, 185, 129, 0.15)', name='Optimal Sweet Spot', hoverinfo='skip'
        )

        fig.add_trace(px.line(chart_df, x="Datum", y="Trainingsbelasting", markers=True).data[0])
        fig.data[-1].line.color = "#FF5500"
        fig.data[-1].line.width = 3
        fig.data[-1].marker.size = 6
        fig.data[-1].marker.color = "#FF5500"

        fig.update_layout(
            xaxis_type="date",
            margin=dict(l=10, r=10, t=10, b=10),
            height=320,
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            font=dict(color="#94a3b8"),
            xaxis=dict(gridcolor="rgba(255,255,255,0.05)", zeroline=False),
            yaxis=dict(gridcolor="rgba(255,255,255,0.05)", zeroline=False),
            showlegend=False
        )
        st.plotly_chart(fig, use_container_width=True)

        # --- RECENTE ACTIVITEITEN FEED ---
        if filtered_activities_list:
            st.subheader("⚡ Recente Activiteiten")

            df_feed = pd.DataFrame(filtered_activities_list)

            date_col = None
            for col in ['Datum', 'date', 'Date', 'DATUM', 'start_date']:
                if col in df_feed.columns:
                    date_col = col
                    break

            if date_col:
                df_feed['parsed_date'] = pd.to_datetime(df_feed[date_col], errors='coerce')
                df_feed = df_feed.sort_values(by='parsed_date', ascending=False)
            else:
                df_feed = df_feed.iloc[::-1]

            for _, act in df_feed.head(3).iterrows():
                act_label = str(act.get('label', act.get('Name', act.get('name', act.get('titel', 'Training')))))

                act_date = None
                if date_col and pd.notna(act.get('parsed_date')):
                    act_date = pd.to_datetime(act['parsed_date']).strftime('%d-%m-%Y')
                else:
                    import re

                    match = re.search(r'\d{2}-\d{2}-\d{4}', act_label)
                    act_date = match.group(0) if match else "Onbekend"

                act_mins = int(round(float(act.get('time_mins', 0)), 0))
                act_cals = int(round(float(act.get('calories', 0)), 0))
                act_load = int(round(float(act.get('load', 0)), 0))

                st.markdown(f"""
                    <div style="background: {card_bg}; border: {card_border}; border-left: 4px solid #FF5500; border-radius: 8px; padding: 12px 16px; margin-bottom: 8px; display: flex; justify-content: space-between; align-items: center;">
                        <div>
                            <span style="font-weight: 600; font-size: 14px; color: {text_main};">{act_label}</span><br>
                            <span style="font-size: 12px; color: {text_sub};">📅 {act_date} &nbsp;•&nbsp; ⏱️ {act_mins} min &nbsp;•&nbsp; 🔥 {act_cals} kcal</span>
                        </div>
                        <div style="text-align: right;">
                            <span style="font-size: 10px; color: {text_sub}; text-transform: uppercase; display: block; font-weight: 600;">Score</span>
                            <span style="font-size: 15px; font-weight: 700; color: #10b981;">{act_load}</span>
                        </div>
                    </div>
                """, unsafe_allow_html=True)

        if weekly_details:
            with st.expander("📋 Bekijk volledige historische tabel per week"):
                df_details = pd.DataFrame(weekly_details)
                st.dataframe(df_details.iloc[::-1], use_container_width=True, hide_index=True)

    with tab_schema:
        render_training_schedule_module(user_goal)

    with tab_nutrition:
        st.subheader("🍎 Voeding- & Hersteladvies")
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

            session_score_val = selected_act['load']

            if any(k in name_lower for k in
                   ["interval", "tempo", "VO2", "race", "wedstrijd", "sprint"]) or session_score_val > 150:
                training_type = "Intensieve Interval- of Temposessie"
                recovery_hours = 36
                recovery_status = "⚡ Explosieve belasting — Goed herstel van glycogeen en spieren aanbevolen."
                meal_cat = "zwaar"
            elif duration > 90 or cals > 850 or session_score_val > 120:
                training_type = "Lange Duurloop (LSD)"
                recovery_hours = 40
                recovery_status = "🟠 Grote duurbelasting — Uitgebreid herstel van vocht en koolhydraten nodig."
                meal_cat = "zwaar"
            elif 450 <= cals <= 700 or 45 <= duration <= 90 or session_score_val > 60:
                training_type = "Solide Duurtraining"
                recovery_hours = 24
                recovery_status = "🟢 Prima training! Je herstelt hier heel vlot van met goede voeding."
                meal_cat = "middel"
            elif 200 <= cals or 25 <= duration < 45 or session_score_val > 30:
                training_type = "Lichte Duurloop / Vlot Rondje"
                recovery_hours = 16
                recovery_status = "🟢 Lekker soepel loopje — Je bent zo weer volledig hersteld!"
                meal_cat = "licht"
            else:
                training_type = "Kort Herstel / Uitlopen"
                recovery_hours = 12
                recovery_status = "🟢 Minimale belasting — Vrijwel direct weer fris."
                meal_cat = "licht"

            st.markdown("### ⏱ Herstelanalyse")
            st.info(
                f"**Sectortype:** {training_type}\n\n**Session Score (SS):** {int(round(session_score_val, 0))} pts\n\n**Advies:** {recovery_status} \n*Verwachte hersteltijd: **ca. {recovery_hours} uur**.*")

            carbs_target = int(cals * 0.55 / 4)
            protein_target = int(st.session_state.body_weight * 0.35)

            st.markdown("### 🎯 Voor (optimaal) herstel ")
            col_m1, col_m2 = st.columns(2)
            col_m1.metric("Koolhydraten aanvullen", f"ca. {carbs_target} gram")
            col_m2.metric("Eiwitten (Spierherstel)", f"ca. {protein_target} gram")

            st.markdown("---")
            st.markdown("### 🍳 Mogelijke recepten")

            recipe_database = {
                "zwaar": [
                    {
                        "title": "Power Haver-Kwark Bowl met Rood Fruit",
                        "kcal": 550, "carbs": 70, "protein": 35,
                        "ingredients": ["70g havermout", "200g magere kwark", "1 banaan", "Handje blauwe bessen",
                                        "1 el chiazaad", "Scheutje honing"],
                        "steps": ["Meng de havermout met de kwark en een scheutje water of melk.",
                                  "Snijd de banaan in plakjes en verdeel samen met het rode fruit, chiazaad en de honing over de bowl."]
                    },
                    {
                        "title": "Volkoren Wrap met Tonijn, Avocado & Bonen",
                        "kcal": 650, "carbs": 60, "protein": 40,
                        "ingredients": ["2 volkoren wraps", "1 blikje tonijn (op water)", "1/2 avocado",
                                        "50g kidneybonen", "Sla en komkommer", "Yoghurt-knoflookdressing"],
                        "steps": ["Prak de avocado en meng met de uitgelekte tonijn en kidneybonen.",
                                  "Leg sla op de wraps, verdeel het tonijnmengsel erover, voeg komkommer toe en rol strak op."]
                    }
                ],
                "middel": [
                    {
                        "title": "Proteïne Yoghurt met Cruesli & Appel",
                        "kcal": 420, "carbs": 50, "protein": 30,
                        "ingredients": ["250ml Griekse yoghurt 0% of Skyr", "40g volkoren granen / cruesli",
                                        "1 appel in stukjes", "Snufje kaneel"],
                        "steps": ["Schep de Skyr in een mooie kom.",
                                  "Voeg de knapperige granen toe, garneer met de stukjes appel en bestrooi met kaneel."]
                    }
                ],
                "licht": [
                    {
                        "title": "Lichte Smoothie van Rood Fruit & Kwark",
                        "kcal": 300, "carbs": 40, "protein": 22,
                        "ingredients": ["150g diepvries rood fruit", "150ml magere kwark",
                                        "100ml water of amandelmelk"],
                        "steps": ["Voeg alle ingrediënten toe aan een blender.",
                                  "Blend tot een gladde, frisse en lichte herstelsmoothie."]
                    }
                ]
            }

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
            st.info(
                f"💡 Geen actieve selectie gevonden; we gebruiken je meest recente activiteit: **{latest_act['name']} ({target_cals_fridge} kcal)**")
        else:
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
            st.info(
                "✂️ Sleep en pas het kader hieronder aan om de foto bij te snijden op de ingrediënten die je wilt gebruiken.")
            cropped_img = st_cropper(
                Image.open(uploaded_image),
                realtime_update=True
            )