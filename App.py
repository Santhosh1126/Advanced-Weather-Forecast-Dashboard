import streamlit as st
import requests
from datetime import datetime, timedelta, timezone 
import plotly.graph_objects as go
import numpy as np
import folium 
from streamlit_folium import folium_static 

# --- Configuration and Setup ---
st.set_page_config(page_title="Weather Dashboard", page_icon="🌤️", layout="wide")
st.title("Weather & Forecast Dashboard 🌤️")
st.write("Enter a city or village name to get detailed real-time conditions, hourly, 5-day forecast, and map view.")

# NOTE: Replace this with your actual OpenWeatherMap API key
API_KEY = "70451a833f8d4af7bb85f2278e3c5afb"

# -------- Helper Functions (Data Fetching - NOW USING FREE-TIER ENDPOINTS) --------
@st.cache_data(ttl=600) 
def get_coordinates(city_name):
    """Fetches latitude, longitude, city name, and country code."""
    url = f"http://api.openweathermap.org/geo/1.0/direct?q={city_name}&limit=1&appid={API_KEY}"
    try:
        response = requests.get(url).json()
        if response:
            return response[0]["lat"], response[0]["lon"], response[0]["name"], response[0].get("country","")
    except (requests.exceptions.RequestException, IndexError):
        return None, None, None, None
    return None, None, None, None

@st.cache_data(ttl=600)
def get_weather_data(lat, lon):
    """
    Fetches data using the standard, free-tier endpoints:
    1. Current Weather (2.5/weather)
    2. 5-Day/3-Hour Forecast (2.5/forecast)
    3. Air Quality Index (2.5/air_pollution)
    
    NOTE: UV Index and Dew Point are NOT available on these free endpoints.
    """
    data = {}
    base_url = "http://api.openweathermap.org/data/2.5/"
    
    # 1. Current Weather API (Provides current, sunrise/sunset, pressure, wind, etc.)
    current_url = f"{base_url}weather?lat={lat}&lon={lon}&appid={API_KEY}&units=metric"
    try:
        data['current'] = requests.get(current_url).json()
        # Extract timezone offset from current data (required for local time display)
        data['timezone_offset'] = data['current'].get('timezone', 0)
    except requests.exceptions.RequestException:
        data['current'] = None

    # 2. 5-Day/3-Hour Forecast API (Provides hourly forecast data)
    forecast_url = f"{base_url}forecast?lat={lat}&lon={lon}&appid={API_KEY}&units=metric"
    try:
        data['forecast'] = requests.get(forecast_url).json()
    except requests.exceptions.RequestException:
        data['forecast'] = None

    # 3. Air Quality Index (Still separate and usually reliable)
    try:
        data['aqi'] = requests.get(f"{base_url}air_pollution?lat={lat}&lon={lon}&appid={API_KEY}").json()
    except requests.exceptions.RequestException:
        data['aqi'] = None
        
    # Check for critical failures based on status codes
    if data['current'] is None or data['forecast'] is None or data['current'].get('cod') != 200:
         return None # Signal a complete failure
        
    return data

# -------- Utility Functions (Remains the same) --------
def m_s_to_km_h(m_s):
    return m_s * 3.6

# UV index metrics are removed as they are not available on free tier
# UV index utility function is now removed.

def get_aqi_category(aqi_value):
    aqi_map = {1:"Good", 2:"Fair", 3:"Moderate", 4:"Poor", 5:"Very Poor"}
    aqi_color_map = {1:"#00e400", 2:"#ffff00", 3:"#ff7e00", 4:"#ff0000", 5:"#99004c"}
    category = aqi_map.get(aqi_value, 'Unknown')
    color = aqi_color_map.get(aqi_value, 'white')
    return category, color

def format_local_time(timestamp, offset):
    # Calculate UTC time from timestamp, then add offset
    local_ts = timestamp + offset
    return datetime.fromtimestamp(local_ts, timezone.utc).strftime("%I:%M %p")

# -------- MAP FUNCTION (Simplified to ensure visibility) --------
def create_weather_map(lat, lon, city_name, current_temp, current_desc, api_key):
    """Creates a Folium map centered on the city with a current weather marker."""
    
    m = folium.Map(location=[lat, lon], zoom_start=10, tiles="CartoDB dark_matter")
    
    html = f"""
    <div style="font-family: Arial, sans-serif; text-align: center;">
        <h4 style="margin:0;">{city_name}</h4>
        <p style="margin:0; font-size: 1.2em;">{current_temp}°C</p>
        <p style="margin:0; font-size: 0.9em;">{current_desc}</p>
    </div>
    """
    iframe = folium.IFrame(html, width=150, height=80)
    popup = folium.Popup(iframe, max_width=2650)
    
    folium.Marker(
        [lat, lon], 
        popup=popup,
        icon=folium.Icon(color='red', icon='cloud', prefix='fa')
    ).add_to(m)

    # NOTE: OpenWeatherMap Tile Layers are still commented out as they often fail on the free tier.
    # We rely on the base map and the marker.
    
    return m

# -------- Streamlit Application Interface (Main Logic) --------
city = st.text_input("Enter City or Village Name", value="Anantapur") # Defaulting to Anantapur for testing

if st.button("Get Weather"):
    if not city.strip():
        st.warning("⚠️ Please enter a city or village name.")
        st.stop()

    # --- Step 1: Get Coordinates ---
    with st.spinner('📍 Locating city...'):
        lat, lon, city_name, country = get_coordinates(city)
        if lat is None:
            st.error("❌ City or village not found. Try a different name.")
            st.stop()
            
    # --- Step 2: Fetch All Data ---
    with st.spinner('🛰️ Fetching real-time weather data and forecast...'):
        all_data = get_weather_data(lat, lon)
        
        # Check for failure from the new data fetching function
        if all_data is None:
            st.error("❌ Could not retrieve complete weather data. Check API key or connection.")
            st.stop()
        
        current = all_data.get('current')
        forecast = all_data.get('forecast') # This is now the 5-day/3-hour forecast
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
        <div style="display: flex; align-items: center; margin-bottom: 5px;">
            <img src="http://openweathermap.org/img/wn/{icon_code}@2x.png" width="80" style="margin-right: -20px;">
            <h1 style="margin:0; font-size: 3em;">{current['main']['temp']:.1f}°C</h1>
        </div>
        <p style="font-size: 1.5em; font-weight: bold; margin-top: -10px;">{description}</p>
        """, unsafe_allow_html=True)
        
        col_m1, col_m2 = st.columns(2)
        wind_kmh = m_s_to_km_h(current.get('wind', {}).get('speed', 0)) # Note the path change
        
        with col_m1:
            st.metric("💨 Wind (km/h)", f"{wind_kmh:.1f} km/h")
            st.metric("💧 Humidity", f"{current['main'].get('humidity', 'N/A')}%")
            st.metric("🌡 Feels Like", f"{current['main'].get('feels_like', 'N/A'):.1f} °C")
            
        with col_m2:
            st.metric("🔵 Pressure", f"{current['main'].get('pressure', 'N/A')} hPa")
            # --- REMOVED: Dew Point (Not on Free API) ---
            st.metric("⬆️ Max Temp", f"{current['main'].get('temp_max', 'N/A'):.1f} °C")
            # --- REMOVED: UV Index (Not on Free API) ---
            st.metric("⬇️ Min Temp", f"{current['main'].get('temp_min', 'N/A'):.1f} °C")


    # --- AQI Card and Sunrise/Sunset (Uses fixed function calls) ---
    with col_aqi:
        st.subheader("💨 Air Quality Index")
        if aqi_data and aqi_data.get("list"):
            aqi_value = aqi_data["list"][0]["main"]["aqi"]
            category, color = get_aqi_category(aqi_value)
            st.markdown(f"""
            <div style="padding: 15px; border-radius: 10px; text-align: center; border: 2px solid {color}; background-color: #1c202a;">
                <h2 style='color:{color}; margin: 0;'>{category}</h2>
                <p style='color: white; margin: 0;'>Index {aqi_value}</p>
            </div>
            """, unsafe_allow_html=True)
        else:
            st.info("AQI data unavailable.")
        
        st.markdown("---")
        
        st.subheader("🌅 Sunrise & Sunset")
        col_sun_rise, col_sun_set = st.columns(2)
        
        sunrise_time = format_local_time(current["sys"].get("sunrise", 0), tz_offset_seconds)
        sunset_time = format_local_time(current["sys"].get("sunset", 0), tz_offset_seconds)

        with col_sun_rise:
            st.markdown(f'<div style="text-align: center;">☀️<p style="font-size: 1.2em; margin: 0;">Sunrise</p><p style="font-size: 1.5em; font-weight: bold; color: #FFA500;">{sunrise_time}</p></div>', unsafe_allow_html=True)
        with col_sun_set:
            st.markdown(f'<div style="text-align: center;">🌙<p style="font-size: 1.2em; margin: 0;">Sunset</p><p style="font-size: 1.5em; font-weight: bold; color: #FFA500;">{sunset_time}</p></div>', unsafe_allow_html=True)
        
        st.markdown('<div style="text-align: center; font-size: 1.5em; padding-top: 10px;">🌄<span style="display:inline-block; width: 80%; border-bottom: 2px dotted #FFA500;"></span>🌃</div>', unsafe_allow_html=True)


    # --- Alerts Card (Now using a placeholder, as alerts require One Call API) ---
    with col_alerts:
        st.subheader("⚠️ Weather Alerts")
        st.markdown('<div style="background-color: #1c202a; padding: 15px; border-radius: 10px; text-align: center; color: #aaa;">Weather Alerts are not available on the free API plan.</div>', unsafe_allow_html=True)


    # --- Step 4: Live World Map Visualization ---
    st.markdown("---")
    st.subheader("🗺️ Live Map: City Location")
    
    weather_map = create_weather_map(lat, lon, city_name, current['main']['temp'], description, API_KEY)
    
    folium_static(weather_map, width=1200, height=500)


    # --- Step 5: 24-Hour Hourly Forecast Graph (Using 3-hour steps from 5-day forecast) ---
    st.markdown("---")
    st.subheader(f"24-Hour Hourly Forecast")
    
    hours, temps, conditions, icons = [], [], [], []
    
    # The 'forecast' list contains 40 entries (5 days * 8 intervals/day)
    for item in forecast['list'][:8]: # Take the first 8 entries (24 hours at 3-hour intervals)
        local_time_ts = item["dt"] + tz_offset_seconds
        hour_label = datetime.fromtimestamp(local_time_ts, timezone.utc).strftime("%I %p").lstrip('0')
        hours.append(hour_label)
        temps.append(item["main"]["temp"]) # Note the path change
        conditions.append(item["weather"][0]["description"].title())
        icons.append(item["weather"][0]["icon"])

    if hours:
        # ... (Hourly Graph Code remains the same) ...
        fig_hourly = go.Figure()
        
        fig_hourly.add_trace(go.Scatter(
            x=hours, y=temps, mode='lines+markers+text',
            text=[f"{t:.1f}°C" for t in temps], textposition="top center",
            line=dict(color='#00BFFF', width=3), marker=dict(size=8, color='#FF4B4B')
        ))

        for i, icon in enumerate(icons):
            fig_hourly.add_layout_image(dict(
                    source=f"http://openweathermap.org/img/wn/{icon}@2x.png",
                    x=hours[i], y=temps[i] + 0.5, xref="x", yref="y",
                    sizex=0.3, sizey=3, xanchor="center", yanchor="bottom", layer="above"
                ))
            fig_hourly.add_annotation(
                x=hours[i], y=temps[i] - 1.5, text=conditions[i].split()[0],
                showarrow=False, font=dict(size=10, color="lightgray")
            )
            
        fig_hourly.update_layout(
            title="", xaxis_title="", yaxis_title="Temperature (°C)",
            template="plotly_dark", height=400, showlegend=False,
            yaxis=dict(range=[min(temps) - 3, max(temps) + 3])
        )
        st.plotly_chart(fig_hourly, use_container_width=True)


    # --- Step 6: 5-Day Daily Forecast (Derived from 3-hour data) ---
    st.markdown("---")
    st.subheader(f"🗓️ 5-Day Daily Forecast")
    
    days, temps_max, temps_min, icons = [], [], [], []
    
    # We aggregate the 3-hour data into 5 days for a clean daily view
    daily_data = {}
    for item in forecast['list']:
        day_name = datetime.fromtimestamp(item["dt"]).strftime("%a")
        temp = item["main"]["temp"]
        icon = item["weather"][0]["icon"]

        if day_name not in daily_data:
            daily_data[day_name] = {'temps': [], 'icon': icon}
        
        daily_data[day_name]['temps'].append(temp)
    
    # Populate the lists for the chart
    for day, data in list(daily_data.items())[:5]: # Only show 5 days
        days.append(day)
        temps_max.append(np.max(data['temps']))
        temps_min.append(np.min(data['temps']))
        icons.append(data['icon'])

    if days:
        # ... (Daily Graph Code remains the same, adjusted for 5 days) ...
        fig_daily = go.Figure()
        
        fig_daily.add_trace(go.Scatter(
            x=days, y=temps_max, name='Max Temp', mode='lines+markers+text',
            text=[f"H: {t:.1f}°C" for t in temps_max], textposition="top center",
            line=dict(color='#FF4B4B', width=3), marker=dict(size=10)
        ))
        
        fig_daily.add_trace(go.Scatter(
            x=days, y=temps_min, name='Min Temp', mode='lines+markers+text',
            text=[f"L: {t:.1f}°C" for t in temps_min], textposition="bottom center",
            line=dict(color='#5D8AA8', width=3, dash='dot'), marker=dict(size=10)
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
            template="plotly_dark", yaxis=dict(range=[np.min(temps_min) - 3, np.max(temps_max) + 5]), 
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