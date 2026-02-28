import os
import math
import folium
import pandas as pd
import streamlit as st
import openrouteservice
from ebird.api import requests as ebird
from itertools import cycle
from folium.plugins import OverlappingMarkerSpiderfier, TreeLayerControl, Fullscreen
from streamlit_folium import st_folium
from openrouteservice import convert

# --- CONFIGURATION ---
try:
    API_KEY_ENV = st.secrets['EBIRD_API_KEY']
    ORS_API_KEY_ENV = st.secrets['ORS_API_KEY']
except:
    API_KEY_ENV = os.getenv('EBIRD_API_KEY')
    ORS_API_KEY_ENV = os.getenv('ORS_API_KEY')
DEFAULT_LIFE_LIST = 'ebird_world_life_list.csv'
RADIUS = 50 
COLORS = ['red', 'blue', 'gray', 'darkred', 'lightred', 'orange', 'beige',
          'green', 'darkgreen', 'lightgreen', 'darkblue', 'lightblue',
          'purple', 'darkpurple', 'pink', 'cadetblue', 'lightgray', 'black']

st.set_page_config(page_title="Lifer Mapper", layout="wide", initial_sidebar_state="expanded")

# CSS: Locked Sidebar, No Margins
st.markdown("""
<style>
    section[data-testid="stSidebar"] { min-width: 278px !important; max-width: 278px !important; width: 278px !important; }
    .block-container { padding: 0rem !important; max-width: 100% !important; height: 100vh !important; margin: 0px !important; }
    header, footer, [data-testid="stHeader"] { display: none !important; visibility: hidden !important; }
    section[data-testid="stSidebar"] div[data-testid="stSidebarHeader"] { display: none !important; }
</style>
""", unsafe_allow_html=True)

# --- MATH UTILS ---
def get_seen_species(uploaded_file, default_path):
    try:
        df = pd.read_csv(uploaded_file if uploaded_file else default_path)
        return set(df['Common Name'].unique())
    except:
        return set()

def get_hex_coords(lat, lon, radius_km):
    points = [(lat, lon)]
    dist = math.sqrt(3) * radius_km 
    for i in range(6):
        angle_rad = math.radians(60 * i)
        d_lat = (dist / 111.32) * math.cos(angle_rad)
        d_lon = (dist / (111.32 * math.cos(math.radians(lat)))) * math.sin(angle_rad)
        points.append((lat + d_lat, lon + d_lon))
    return points

def get_line_coords(start, end, radius_km):
    lat1, lon1 = start
    lat2, lon2 = end
    R_earth = 6371
    dlat, dlon = math.radians(lat2 - lat1), math.radians(lon2 - lon1)
    a = math.sin(dlat/2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon/2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
    total_dist = R_earth * c
    gapless_step = radius_km * math.sqrt(2)
    steps = max(1, math.ceil(total_dist / gapless_step))
    return [(lat1 + (lat2 - lat1) * (i/steps), lon1 + (lon2 - lon1) * (i/steps)) for i in range(steps + 1)]

def get_ors_route_coords(start, end, radius_km, api_key):
    """Fetches real road geometry and samples points for gapless coverage."""
    client = openrouteservice.Client(key=api_key)
    
    # ORS expects [lon, lat]
    coords = ((start[1], start[0]), (end[1], end[0]))
    
    # Get driving route
    route = client.directions(coordinates=coords, profile='driving-car', format='geojson')
    geometry = route['features'][0]['geometry']['coordinates']
    
    # geometry is a list of [lon, lat] points along the road
    # We sample these points to ensure we scan at the correct interval
    sampled_points = []
    accumulated_dist = 0
    gapless_step = radius_km * math.sqrt(2) # ~70.7km
    
    # Start with the first point
    last_pt = (geometry[0][1], geometry[0][0])
    sampled_points.append(last_pt)
    
    for i in range(1, len(geometry)):
        curr_pt = (geometry[i][1], geometry[i][0])
        # Simple Euclidean approximation for sampling distance between road nodes
        dist = math.sqrt((curr_pt[0]-last_pt[0])**2 + (curr_pt[1]-last_pt[1])**2) * 111
        accumulated_dist += dist
        
        if accumulated_dist >= gapless_step:
            sampled_points.append(curr_pt)
            accumulated_dist = 0
        last_pt = curr_pt
        
    # Ensure the destination is included
    dest_pt = (geometry[-1][1], geometry[-1][0])
    if sampled_points[-1] != dest_pt:
        sampled_points.append(dest_pt)
        
    return sampled_points, geometry

# --- SESSION STATE ---
if 'search_results' not in st.session_state: st.session_state.search_results = None
if 'center' not in st.session_state: st.session_state.center = [35.0, -100.0]
if 'zoom' not in st.session_state: st.session_state.zoom = 4
if 'scan_mode' not in st.session_state: st.session_state.scan_mode = None 
if 'road_points' not in st.session_state: st.session_state.road_points = []
if 'pending_road' not in st.session_state: st.session_state.pending_road = False
if 'pending_road_points' not in st.session_state: st.session_state.pending_road_points = []
if 'pending_search_points' not in st.session_state: st.session_state.pending_search_points = None

with st.sidebar:
    st.title("Lifer Mapper")
    user_api_key = st.text_input(
        "eBird API Key",
        value=API_KEY_ENV if API_KEY_ENV else "",
        type="password",
        help="""
Get your free API key from the eBird developer portal:

1. Log in to eBird
2. Visit: https://ebird.org/api/keygen
3. Generate and copy your key
4. Paste it here

Required to fetch bird observations.
"""
    )

    ors_key = st.text_input(
        "OpenRouteService API Key",
        value=ORS_API_KEY_ENV if ORS_API_KEY_ENV else "",
        type="password",
        help="""
Get a free OpenRouteService key:

1. Create an account at https://openrouteservice.org
2. Go to Dashboard → API Keys
3. Create a new token
4. Paste it here

Required for Road Trip routing.
"""
    )

    uploaded_csv = st.file_uploader(
        "Upload Life List (.csv)",
        type=["csv"],
        help="""
Upload your personal life list from eBird:

How to export:
1. Log in to eBird
2. Go to My eBird → Sightings List
3. Click “Download Data”
4. Save as CSV
5. Upload the file here

If no file is provided, all species will be reported.
"""
    )    

    BACK_DAYS = st.select_slider(
        "Back Days",
        options=[1, 3, 7, 14, 30],
        value=14,
        help="How many days back to search for sightings"
    )

    col1, col2 = st.columns(2)

    with col1:
        if st.button(
            "🎯 Hex Scan",
            use_container_width=True,
            type="primary" if st.session_state.scan_mode == 'hex' else "secondary",
            help="""
    Hex Scan Mode:
    • Click one point on the map
    • Scans a hexagonal grid around that location out to a radius of 136.6km
    """
        ):
            st.session_state.scan_mode = 'hex'
            st.rerun()

    with col2:
        if st.button(
            "🚗 Road Trip",
            use_container_width=True,
            type="primary" if st.session_state.scan_mode == 'road' else "secondary",
            help="""
    Road Trip Mode:
    • Click a START point
    • Click an END point
    • Scans along the real driving route
    • Finds lifers within 50 km of the road
    """
        ):
            st.session_state.scan_mode = 'road'
            st.session_state.road_points = []
            st.rerun()

    if st.session_state.scan_mode == 'hex':
        st.info("🎯 Map Armed: Click one point to scan.")
    elif st.session_state.scan_mode == 'road':
        count = len(st.session_state.road_points)
        if count == 0:
            st.info("🚗 Road Trip: Click the START point.")
        elif count == 1:
            st.warning("🚗 Road Trip (1/2 Selected): Click the END point.")
        elif st.session_state.pending_road:
            st.info("Route ready. Click 'Compute Route & Scan' to continue.")

    # If a route has been selected but not yet computed, show a button to compute it
    if st.session_state.pending_road:
        if st.button("Compute Route & Scan", use_container_width=True):
            if not ors_key:
                st.error("Please enter an OpenRouteService API Key in the sidebar.")
            else:
                try:
                    search_points, road_geometry = get_ors_route_coords(
                        st.session_state.pending_road_points[0],
                        st.session_state.pending_road_points[1],
                        RADIUS, ors_key
                    )
                    st.session_state.road_geometry = road_geometry
                    st.session_state.pending_road = False
                    st.session_state.pending_road_points = []
                    st.session_state.pending_search_points = search_points
                    st.session_state.scan_mode = None
                    st.rerun()
                except Exception as e:
                    st.error(f"Routing Error: {e}")
 
    status_placeholder = st.empty()

    # METRICS LOGIC
    if st.session_state.search_results:
        res = st.session_state.search_results
        total_sightings = sum(len(sightings) for sightings in res['species_map'].values())
        total_species = len(res['species_map'])
        
        st.metric("Unique Sightings", total_sightings)
        st.metric("Target Species", total_species)

    if st.button("❌ Reset / Clear Map", use_container_width=True):
        st.session_state.scan_mode, st.session_state.road_points, st.session_state.search_results = None, [], None
        st.session_state.pending_road = False
        st.session_state.pending_road_points = []
        st.session_state.pending_search_points = None
        if 'road_geometry' in st.session_state: del st.session_state['road_geometry']
        st.rerun()

# --- MAP RENDERING ---
m = folium.Map(location=st.session_state.center, zoom_start=st.session_state.zoom, tiles=None)
folium.TileLayer('OpenStreetMap', control=False).add_to(m)
Fullscreen().add_to(m)

spider = OverlappingMarkerSpiderfier(keep_spiderfied=True, nearby_distance=20)

if st.session_state.search_results:
    res = st.session_state.search_results
    color_cycle = cycle(COLORS)
    lifer_groups = {}
    
    grid_group = folium.FeatureGroup(name="Search Boundaries")
    for pt in res['points']:
        folium.Circle(pt, radius=RADIUS*1000, color='royalblue', weight=1, fill=True, fill_opacity=0.05).add_to(grid_group)
    grid_group.add_to(m)

    for sp_code, bird_list in res['species_map'].items():
        com_name = bird_list[0]['comName']
        fg = folium.FeatureGroup(name=com_name)
        color = next(color_cycle)
        for bird in bird_list:
            popup_html = f"<div style='font-family: Arial; width: 200px;'><h4 style='margin-bottom:5px;'>{bird['comName']}</h4><b>Date:</b> {bird['obsDt']}<br><b>Location:</b> {bird['locName']}<br><b>Count:</b> {bird.get('howMany', 'N/A')}<br><a href='https://ebird.org/checklist/{bird['subId']}' target='_blank'>View Checklist</a></div>"
            folium.Marker(location=[bird['lat'], bird['lng']], popup=folium.Popup(popup_html, max_width=250), tooltip=com_name, icon=folium.Icon(color=color, icon='binoculars', prefix='fa')).add_to(fg)
        fg.add_to(m)
        lifer_groups[com_name] = fg

    overlay_tree = {"label": "Map Overlays", "children": [{"label": "Search Grid", "layer": grid_group}, {"label": "Potential Lifers", "select_all_checkbox": "Select/Unselect All", "children": [{"label": name, "layer": group} for name, group in sorted(lifer_groups.items())]}]}
    TreeLayerControl(overlay_tree=overlay_tree, collapsed=False).add_to(m)
    spider.add_to(m)
    folium.FitOverlays().add_to(m)

map_data = st_folium(m, height=1000, use_container_width=True, key="mapper")

# --- SCAN LOGIC ---
# Trigger scanning either via an armed map click (hex/road) or via a pending search computed from the sidebar
if (st.session_state.scan_mode and map_data.get("last_clicked")) or st.session_state.pending_search_points:
    search_points = []

    # If a computed route/search was queued, use it
    if st.session_state.pending_search_points:
        search_points = st.session_state.pending_search_points
        st.session_state.pending_search_points = None
    else:
        click = (map_data["last_clicked"]["lat"], map_data["last_clicked"]["lng"])
        if st.session_state.scan_mode == 'hex':
            search_points = get_hex_coords(click[0], click[1], RADIUS)
        elif st.session_state.scan_mode == 'road':
            if click not in st.session_state.road_points:
                st.session_state.road_points.append(click)
                if len(st.session_state.road_points) == 2:
                    # Defer heavy routing call until user confirms — prevents UI hang on click
                    st.session_state.pending_road = True
                    st.session_state.pending_road_points = st.session_state.road_points.copy()
                    # Keep the selected points visible; user must click the Compute button to proceed
                    st.rerun()
                else:
                    st.rerun()

    if search_points:
        with status_placeholder.container():
            st.markdown("### 🛰️ Scanning...")
            progress_bar = st.progress(0)
            progress_text = st.empty()

            current_api_key = user_api_key if user_api_key else API_KEY_ENV
            seen_species = get_seen_species(uploaded_csv, DEFAULT_LIFE_LIST)
            species_map = {}
            total = len(search_points)
            for idx, (pt_lat, pt_lng) in enumerate(search_points):
                obs = ebird.get_nearby_observations(current_api_key, pt_lat, pt_lng, dist=RADIUS, back=BACK_DAYS, category='species')
                lifers = [o for o in obs if o['comName'] not in seen_species and o.get('exoticCategory') != 'X']
                for sp in lifers:
                    s_code = sp['speciesCode']
                    specifics = ebird.get_nearest_species(current_api_key, s_code, pt_lat, pt_lng, dist=RADIUS, back=BACK_DAYS)
                    if s_code not in species_map: species_map[s_code] = []
                    for b in specifics:
                        if not any(existing['subId'] == b['subId'] for existing in species_map[s_code]):
                            species_map[s_code].append(b)

                # Update progress UI
                pct = int(((idx + 1) / total) * 100)
                progress_bar.progress(pct)
                progress_text.markdown(f"Scanned **{idx + 1}/{total}** sections")

            # Ensure final state reflects completion
            progress_bar.progress(100)
            progress_text.markdown(f"Scanned **{total}/{total}** sections — complete")

            st.session_state.search_results = {'points': search_points, 'species_map': species_map}
            st.session_state.scan_mode, st.session_state.road_points = None, []
            st.rerun()




