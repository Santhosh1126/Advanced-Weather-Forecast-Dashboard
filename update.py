import streamlit as st
import requests
from datetime import datetime, timedelta, timezone 
import plotly.graph_objects as go
import numpy as np
import folium 
from streamlit_folium import folium_static 

# ----------------------------------------------------------------------
# --- Configuration and Setup ---
# ----------------------------------------------------------------------

# NOTE: Replace this with your actual OpenWeatherMap API key
# *** KEEP YOUR API KEY PRIVATE ***
API_KEY = "70451a833f8d4af7bb85f2278e3c5afb" 

# --- Session State and Theme Management ---
if 'theme' not in st.session_state:
    st.session_state.theme = 'light' 
if 'city_name' not in st.session_state:
    st.session_state.city_name = "Anantapur" # Default City
if 'weather_data' not in st.session_state:
    st.session_state.weather_data = None
if 'city_search_done' not in st.session_state:
    st.session_state.city_search_done = False

current_theme = st.session_state.theme
plotly_template = "plotly_white" if current_theme == 'light' else "plotly_dark"

def toggle_theme():
    """Toggles the theme state."""
    if st.session_state.theme == 'light':
        st.session_state.theme = 'dark'
    else:
        st.session_state.theme = 'light'

# Define color variables based on the current theme for consistency in HTML/Markdown
TEXT_COLOR = "#333333" if current_theme == 'light' else "white"
CARD_BG_COLOR = "#f0f2f6" if current_theme == 'light' else "#1c202a"
CARD_BORDER_COLOR = "#ddd" if current_theme == 'light' else "#333333"


# --- Page Configuration and Title ---
st.set_page_config(
    page_title="Advanced Weather Dashboard", 
    page_icon="🌤️", 
    layout="wide",
    initial_sidebar_state="collapsed",
)

st.title("⚡ Advanced Weather & Forecast Dashboard")

# 1. Theme Toggle Button in Header
col_header, col_button = st.columns([4, 1])

with col_header:
    st.write("Enter a city or village name to get detailed real-time conditions, hourly, 5-day forecast, and map view.")

with col_button:
    if current_theme == 'light':
        icon = "🌙 Switch to Dark Mode"
    else:
        icon = "💡 Switch to Light Mode"
        
    st.button(icon, on_click=toggle_theme, key="theme_toggle")

# ----------------------------------------------------------------------
# -------- Helper Functions (Data Fetching & Utilities) ----------------
# ----------------------------------------------------------------------

@st.cache_data(ttl=600) 
def get_coordinates(city_name):
    """Fetches latitude, longitude, city name, and country code."""
    url = f"http://api.openweathermap.org/geo/1.0/direct?q={city_name}&limit=1&appid={API_KEY}"
    try:
        response = requests.get(url).json()
        if response and response[0].get("lat") is not None:
            return response[0]["lat"], response[0]["lon"], response[0]["name"], response[0].get("country","")
    except (requests.exceptions.RequestException, IndexError, KeyError):
        pass
    return None, None, None, None

@st.cache_data(ttl=600)
def get_weather_data(lat, lon):
    """Fetches Current, 5-Day/3-Hour Forecast, and Air Quality Index."""
    data = {}
    base_url = "http://api.openweathermap.org/data/2.5/"
    
    current_url = f"{base_url}weather?lat={lat}&lon={lon}&appid={API_KEY}&units=metric"
    try:
        data['current'] = requests.get(current_url).json()
        data['timezone_offset'] = data['current'].get('timezone', 0)
    except requests.exceptions.RequestException:
        data['current'] = None

    forecast_url = f"{base_url}forecast?lat={lat}&lon={lon}&appid={API_KEY}&units=metric"
    try:
        data['forecast'] = requests.get(forecast_url).json()
    except requests.exceptions.RequestException:
        data['forecast'] = None

    try:
        data['aqi'] = requests.get(f"{base_url}air_pollution?lat={lat}&lon={lon}&appid={API_KEY}").json()
    except requests.exceptions.RequestException:
        data['aqi'] = None
        
    if data['current'] is None or data['forecast'] is None or data['current'].get('cod') != 200:
          return None 
        
    return data

def m_s_to_km_h(m_s):
    return m_s * 3.6

def get_aqi_category(aqi_value):
    aqi_map = {1:"Good", 2:"Fair", 3:"Moderate", 4:"Poor", 5:"Very Poor"}
    aqi_color_map = {1:"#00aa00", 2:"#aaaa00", 3:"#cc5500", 4:"#cc0000", 5:"#77004c"}
    category = aqi_map.get(aqi_value, 'Unknown')
    color = aqi_color_map.get(aqi_value, '#333333')
    return category, color

def format_local_time(timestamp, offset):
    local_ts = timestamp + offset
    return datetime.fromtimestamp(local_ts, timezone.utc).strftime("%I:%M %p")

def create_weather_map(lat, lon, city_name, current_temp, current_desc, api_key, theme):
    """
    Creates a Folium map centered on the city, adjusting tiles based on theme 
    and adding the OWM Clouds layer.
    """
    map_tiles = "OpenStreetMap" if theme == 'light' else "CartoDB dark_matter"
    
    TEXT_COLOR_CARD = "black" if theme == 'light' else "white"
    CARD_BG_COLOR_CARD = "white" if theme == 'light' else "#222222" 
    CARD_BORDER_COLOR_CARD = "#ddd" if theme == 'light' else "#444444"
    
    m = folium.Map(location=[lat, lon], zoom_start=10, tiles=map_tiles)
    
    html = f"""
    <div style="font-family: Arial, sans-serif; text-align: center; color: {TEXT_COLOR_CARD}; background-color: {CARD_BG_COLOR_CARD}; border-radius: 5px; padding: 5px; border: 1px solid {CARD_BORDER_COLOR_CARD};">
        <h4 style="margin:0; color: {TEXT_COLOR_CARD};">{city_name}</h4>
        <p style="margin:0; font-size: 1.2em; color: {TEXT_COLOR_CARD};">{current_temp:.1f}°C</p>
        <p style="margin:0; font-size: 0.9em; color: {TEXT_COLOR_CARD};">{current_desc}</p>
    </div>
    """
    iframe = folium.IFrame(html, width=150, height=80)
    popup = folium.Popup(iframe, max_width=2650)
    
    folium.Marker(
        [lat, lon], 
        popup=popup,
        icon=folium.Icon(color='red', icon='cloud', prefix='fa')
    ).add_to(m)

    folium.TileLayer(
        tiles=f'https://tile.openweathermap.org/map/clouds_new/{{z}}/{{x}}/{{y}}.png?appid={api_key}',
        attr='OpenWeatherMap',
        name='Current Clouds',
        overlay=True,
        control=True,
        opacity=0.6
    ).add_to(m)

    folium.LayerControl().add_to(m)
    
    return m

# --- Function to handle the initial data load and store it in state ---
def fetch_and_store_data(city_input):
    """Fetches weather data for a given city and stores it in session_state."""
    if not city_input.strip():
        st.error("⚠️ Please enter a city or village name.")
        return

    with st.spinner(f'📍 Locating and fetching data for {city_input}...'):
        lat, lon, city_name_found, country = get_coordinates(city_input)
        
        if lat is None:
            st.session_state.weather_data = None
            st.session_state.city_search_done = False
            st.error("❌ City or village not found. Try a different name.")
            return
            
        all_data = get_weather_data(lat, lon)
        
        if all_data is None:
            st.session_state.weather_data = None
            st.session_state.city_search_done = False
            st.error("❌ Could not retrieve complete weather data. Check API key or connection.")
            return
        
        # Store the data and key metadata in session state
        st.session_state.weather_data = all_data
        st.session_state.city_name = city_name_found # Update city name with official spelling
        st.session_state.country = country
        st.session_state.lat = lat
        st.session_state.lon = lon
        st.session_state.city_search_done = True
        

# ----------------------------------------------------------------------
# -------- Streamlit Application Interface (Main Logic) ----------------
# ----------------------------------------------------------------------

# --- City Input & Button ---
col_city_input, col_city_button = st.columns([3, 1])

with col_city_input:
    city_input = st.text_input(
        "Enter City or Village Name", 
        value=st.session_state.city_name,
        key="city_input_key"
    )

with col_city_button:
    st.write("") # Spacer for alignment
    st.write("") # Spacer for alignment
    if st.button("Get Weather", key="fetch_button"):
        fetch_and_store_data(city_input)
        

# --- Conditional Display of Dashboard ---
if st.session_state.city_search_done and st.session_state.weather_data:
    
    # Extract data from session state for cleaner code below
    all_data = st.session_state.weather_data
    city_name = st.session_state.city_name
    country = st.session_state.country
    lat = st.session_state.lat
    lon = st.session_state.lon
    
    current = all_data.get('current')
    forecast = all_data.get('forecast')
    aqi_data = all_data.get('aqi')
    tz_offset_seconds = all_data.get('timezone_offset', 0)
    
    # --- Step 3: Top Row: Current, AQI, Alerts ---
    st.subheader(f"📍 Current Conditions in {city_name}, {country}")
    
    col_current, col_aqi, col_alerts = st.columns([1,1,1])

    # --- Current Weather Card (Detailed Metrics) ---
    with col_current:
        icon_code = current.get("weather", [{}])[0].get("icon", "01d")
        description = current.get("weather", [{}])[0].get("description", "Clear").title()
        
        st.markdown(f"""
        <div style="display: flex; align-items: center; margin-bottom: 5px; color: {TEXT_COLOR};">
            <img src="http://openweathermap.org/img/wn/{icon_code}@2x.png" width="80" style="margin-right: -20px;">
            <h1 style="margin:0; font-size: 3em; color: {TEXT_COLOR};">{current['main']['temp']:.1f}°C</h1>
        </div>
        <p style="font-size: 1.5em; font-weight: bold; margin-top: -10px; color: {TEXT_COLOR};">{description}</p>
        """, unsafe_allow_html=True)
        
        col_m1, col_m2 = st.columns(2)
        
        wind_kmh = m_s_to_km_h(current.get('wind', {}).get('speed', 0)) 
        visibility_km = current.get('visibility', 0) / 1000.0 

        with col_m1:
            st.metric("💨 Wind (km/h)", f"{wind_kmh:.1f} km/h")
            st.metric("💧 Humidity", f"{current['main'].get('humidity', 'N/A')}%")
            st.metric("🌡 Feels Like", f"{current['main'].get('feels_like', 'N/A'):.1f} °C")
            
        with col_m2:
            st.metric("🔵 Pressure", f"{current['main'].get('pressure', 'N/A')} hPa")
            st.metric("⬆️ Max Temp", f"{current['main'].get('temp_max', 'N/A'):.1f} °C")
            st.metric("⬇️ Min Temp", f"{current['main'].get('temp_min', 'N/A'):.1f} °C")
            st.metric("👁️ **Visibility (km)**", f"**{visibility_km:.1f} km**") 


    # --- AQI Card and Sunrise/Sunset ---
    with col_aqi:
        st.subheader("💨 Air Quality Index")
        if aqi_data and aqi_data.get("list"):
            aqi_value = aqi_data["list"][0]["main"]["aqi"]
            category, color = get_aqi_category(aqi_value)
            st.markdown(f"""
            <div style="padding: 15px; border-radius: 10px; text-align: center; border: 2px solid {color}; background-color: {CARD_BG_COLOR};">
                <h2 style='color:{color}; margin: 0;'>{category}</h2>
                <p style='color: {TEXT_COLOR}; margin: 0;'>Index {aqi_value}</p>
            </div>
            """, unsafe_allow_html=True)
        else:
            st.info("AQI data unavailable.")
        
        st.markdown("---")
        
        st.subheader("🌅 Sunrise & Sunset")
        col_sun_rise, col_sun_set = st.columns(2)
        
        sunrise_time = format_local_time(current["sys"].get("sunrise", 0), tz_offset_seconds)
        sunset_time = format_local_time(current["sys"].get("sunset", 0), tz_offset_seconds)

        SUN_COLOR = "#FF8C00" 
        with col_sun_rise:
            st.markdown(f'<div style="text-align: center; color: {TEXT_COLOR};">☀️<p style="font-size: 1.2em; margin: 0;">Sunrise</p><p style="font-size: 1.5em; font-weight: bold; color: {SUN_COLOR};">{sunrise_time}</p></div>', unsafe_allow_html=True)
        with col_sun_set:
            st.markdown(f'<div style="text-align: center; color: {TEXT_COLOR};">🌙<p style="font-size: 1.2em; margin: 0;">Sunset</p><p style="font-size: 1.5em; font-weight: bold; color: {SUN_COLOR};">{sunset_time}</p></div>', unsafe_allow_html=True)
        
        st.markdown(f'<div style="text-align: center; font-size: 1.5em; padding-top: 10px;">🌄<span style="display:inline-block; width: 80%; border-bottom: 2px dotted {SUN_COLOR};"></span>🌃</div>', unsafe_allow_html=True)


    # --- Alerts Card ---
    with col_alerts:
        st.subheader("⚠️ Weather Alerts")
        st.markdown(f'<div style="background-color: {CARD_BG_COLOR}; padding: 15px; border-radius: 10px; text-align: center; color: {TEXT_COLOR}; border: 1px solid {CARD_BORDER_COLOR};">Weather Alerts are not available on the free API plan.</div>', unsafe_allow_html=True)


    # --- Step 4: Live World Map Visualization ---
    st.markdown("---")
    st.subheader("🗺️ Live Map: City Location & Cloud Layer")
    
    weather_map = create_weather_map(lat, lon, city_name, current['main']['temp'], description, API_KEY, current_theme)
    
    folium_static(weather_map, width=1200, height=500)


    # --- Step 5: Hourly Forecast Graph (With Interactive Slider) ---
    st.markdown("---")
    
    hours_to_show = st.slider(
        "Select number of hours for detailed forecast:",
        min_value=3, 
        max_value=48, 
        value=24, 
        step=3,
        key='hourly_slider_main'
    )
    num_chunks = hours_to_show // 3

    st.subheader(f"Hourly Forecast (Next {hours_to_show} Hours)")

    hours, temps, conditions, icons = [], [], [], []
    
    for item in forecast['list'][:num_chunks]: 
        local_time_ts = item["dt"] + tz_offset_seconds
        
        # 🟢 FIX APPLIED HERE: Including "%a" (Abbreviated Day Name)
        hour_label = datetime.fromtimestamp(local_time_ts, timezone.utc).strftime("%a %I %p").lstrip('0')
        
        hours.append(hour_label)
        temps.append(item["main"]["temp"]) 
        conditions.append(item["weather"][0]["description"].title())
        icons.append(item["weather"][0]["icon"])

    if hours:
        fig_hourly = go.Figure()
        
        line_color = '#0077CC' 
        marker_color = '#FF5733' 
        text_color_plot = 'gray' if current_theme == 'light' else 'lightgray'

        fig_hourly.add_trace(go.Scatter(
            x=hours, y=temps, mode='lines+markers+text',
            text=[f"{t:.1f}°C" for t in temps], textposition="top center",
            line=dict(color=line_color, width=3), 
            marker=dict(size=8, color=marker_color) 
        ))

        for i, icon in enumerate(icons):
            fig_hourly.add_layout_image(dict(
                        source=f"http://openweathermap.org/img/wn/{icon}@2x.png",
                        x=hours[i], y=temps[i] + 0.5, xref="x", yref="y",
                        sizex=0.3, sizey=3, xanchor="center", yanchor="bottom", layer="above"
                    ))
            fig_hourly.add_annotation(
                x=hours[i], y=temps[i] - 1.5, text=conditions[i].split()[0],
                showarrow=False, font=dict(size=10, color=text_color_plot)
            )
            
        fig_hourly.update_layout(
            title="", xaxis_title="", yaxis_title="Temperature (°C)",
            template=plotly_template, 
            height=400, showlegend=False,
            yaxis=dict(range=[min(temps) - 3, max(temps) + 3])
        )
        st.plotly_chart(fig_hourly, use_container_width=True)


    # --- Step 6: 5-Day Daily Forecast ---
    st.markdown("---")
    st.subheader(f"🗓️ 5-Day Daily Forecast")
    
    days, temps_max, temps_min, icons = [], [], [], []
    
    daily_data = {}
    for item in forecast['list']:
        day_name = datetime.fromtimestamp(item["dt"]).strftime("%a")
        temp = item["main"]["temp"]
        hour = datetime.fromtimestamp(item["dt"]).hour
        icon = item["weather"][0]["icon"]

        if day_name not in daily_data:
            daily_data[day_name] = {'temps': [], 'icon': icon, 'noon_diff': 24} 
        
        daily_data[day_name]['temps'].append(temp)
        
        current_noon_diff = abs(12 - hour)
        if current_noon_diff < daily_data[day_name]['noon_diff']:
             daily_data[day_name]['icon'] = icon
             daily_data[day_name]['noon_diff'] = current_noon_diff
    
    for day, data in list(daily_data.items())[:5]: 
        days.append(day)
        temps_max.append(np.max(data['temps']))
        temps_min.append(np.min(data['temps']))
        icons.append(data['icon'])

    if days:
        fig_daily = go.Figure()
        
        max_color = '#FF5733'
        min_color = '#337AFF'

        fig_daily.add_trace(go.Scatter(
            x=days, y=temps_max, name='Max Temp', mode='lines+markers+text',
            text=[f"H: {t:.1f}°C" for t in temps_max], textposition="top center",
            line=dict(color=max_color, width=3), 
            marker=dict(size=10)
        ))
        
        fig_daily.add_trace(go.Scatter(
            x=days, y=temps_min, name='Min Temp', mode='lines+markers+text',
            text=[f"L: {t:.1f}°C" for t in temps_min], textposition="bottom center",
            line=dict(color=min_color, width=3, dash='dot'), 
            marker=dict(size=10)
        ))

        mid_temps = np.array([(temps_max[i] + temps_min[i]) / 2 for i in range(len(days))])
        
        for i, icon in enumerate(icons):
            icon_y_offset = 1.5 
            fig_daily.add_layout_image(dict(
                        source=f"http://openweathermap.org/img/wn/{icon}@2x.png",
                        x=days[i], y=mid_temps[i] + icon_y_offset, xref="x", yref="y",
                        sizex=0.35, sizey=4, xanchor="center", yanchor="bottom", layer="above"
                    ))

        fig_daily.update_layout(
            title="", xaxis_title="Day", yaxis_title="Temperature (°C)",
            template=plotly_template, 
            yaxis=dict(range=[np.min(temps_min) - 3, np.max(temps_max) + 5]), 
            height=500
        )
        st.plotly_chart(fig_daily, use_container_width=True)

    # --- Step 7: Data Update Time ---
    st.markdown("---")
    updated_ts = current.get('dt', 0)
    local_updated_ts = updated_ts + tz_offset_seconds
    
    updated_time = datetime.fromtimestamp(local_updated_ts, timezone.utc).strftime('%Y-%m-%d %H:%M')
    
    offset_hours = tz_offset_seconds / 3600
    offset_minutes = (tz_offset_seconds % 3600) / 60
    sign = '+' if offset_hours >= 0 else '-'
    offset_display = f"UTC{sign}{abs(int(offset_hours)):02d}:{abs(int(offset_minutes)):02d}"
    
    st.info(f"📆 Data last updated: {updated_time} Local Time ({offset_display})")