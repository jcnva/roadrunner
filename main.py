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
COLORS = ['red', 'blue', 'gray', 'darkred', 'lightred', 'orange', 'beige',
          'green', 'darkgreen', 'lightgreen', 'darkblue', 'lightblue',
          'purple', 'darkpurple', 'pink', 'cadetblue', 'lightgray', 'black']

st.set_page_config(page_title="Roadrunner", layout="wide", page_icon='roadrunner.png', initial_sidebar_state="expanded")

# CSS: Locked Sidebar, No Margins
st.logo(image='roadrunner.png', size='large')
st.markdown("""
<style>
    section[data-testid="stSidebar"] { width: 278px; }
    section[data-testid="stSidebar"] div[data-testid="stMarkdownContainer"] h1 { padding-top: 0 !important; margin: 0 !important; }
    .block-container { padding: 0px; padding-top: 1rem; max-width: 100%; height: 100vh; margin: 0px; }
    header[data-testid="stHeader"] { height: 2rem ; min-height: 2rem; }
    section[data-testid="stSidebar"] div[data-testid="stSidebarHeader"] { height: 30px; }
    section[data-testid="stSidebar"] div[data-testid="stSidebarUserContent"] { padding-bottom: 1rem !important; }
</style>
""", unsafe_allow_html=True)

# --- MATH UTILS ---
@st.cache_data(show_spinner=False)
def fetch_checklist(api_key, subid):
    return ebird.get_checklist(api_key, subid)

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
    route = client.directions(coordinates=coords, profile='driving-car', format='geojson', radiuses=[-1,-1])
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
    st.title("Roadrunner")
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

    RADIUS = st.select_slider(
        "Radius (km)",
        options=[2, 5, 10, 20, 50],
        value=50
    )

    BACK_DAYS = st.select_slider(
        "Time period (days ago)",
        options=[1, 3, 7, 14, 30],
        value=3
    )

    # --- Updated Scan Buttons with Validation ---

    # Define the condition: buttons are disabled if the key is empty
    # This checks both the manual input and the environment fallback
    is_api_key_missing = not (user_api_key)

    col1, col2, col3 = st.columns(3)

    with col1:
        if st.button(
            "📍 Single Scan",
            use_container_width=True,
            type="primary" if st.session_state.scan_mode == 'single' else "secondary",
            disabled=is_api_key_missing, # Disable if no key
            help="Enter an eBird API key to enable." if is_api_key_missing else """
                • Click one point on the map
                • Scans ONLY that location (50km radius maximum)
                """
        ):
            st.session_state.scan_mode = 'single'
            st.rerun()

    with col2:
        if st.button(
            "🎯 Hex Scan",
            use_container_width=True,
            type="primary" if st.session_state.scan_mode == 'hex' else "secondary",
            disabled=is_api_key_missing, # Disable if no key
            help="Enter an eBird API key to enable." if is_api_key_missing else """
                • Click one point on the map
                • Scans a hexagonal grid around that location (136km radius maximum)
                """
        ):
            st.session_state.scan_mode = 'hex'
            st.rerun()

    with col3:
        # Road Trip requires both eBird AND ORS keys
        is_ors_missing = not (ors_key)
        road_disabled = is_api_key_missing or is_ors_missing
        
        if st.button(
            "🚗 Road Trip",
            use_container_width=True,
            type="primary" if st.session_state.scan_mode == 'road' else "secondary",
            disabled=road_disabled, # Disable if either key is missing
            help="Enter eBird and ORS keys to enable." if road_disabled else """
                • Click a START point
                • Click an END point
                • Scans along the real driving route
                """
        ):
            st.session_state.scan_mode = 'road'
            st.session_state.road_points = []
            st.rerun()

    # Optional: Add a warning message if keys are missing
    if is_api_key_missing:
        st.caption("⚠️ **Buttons disabled:** Please provide an eBird API key above.")    
    
    if st.session_state.scan_mode == 'single':
        st.info("📍 Map Armed: Click one point to scan that location.")
    elif st.session_state.scan_mode == 'hex':
        st.info("🎯 Map Armed: Click one point to scan hex grid.")
    elif st.session_state.scan_mode == 'road':
        count = len(st.session_state.road_points)
        if count == 0:
            st.info("🚗 Road Trip: Click the START point.")
        elif count == 1:
            st.warning("🚗 Road Trip (1/2 Selected): Click the END point.")
        #elif st.session_state.pending_road:
            #st.info("Route ready. Click 'Compute Route & Scan' to continue.")

    # If a route has been selected but not yet computed, show a button to compute it
    if st.session_state.pending_road:
        #if st.button("Compute Route & Scan", use_container_width=True):
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

        col1, col2 = st.columns(2) 

        with col1:
            st.metric("Unique Sightings", total_sightings)
        with col2:
            st.metric("Target Species", total_species)

    if st.session_state.search_results and "current_map" in st.session_state:
        map_html = st.session_state.current_map.get_root().render()

        st.download_button(
            "💾 Save Map as HTML",
            map_html,
            mime="text/html",
            use_container_width=True
        )

    if st.button("❌ Reset / Clear Map", use_container_width=True):
        st.session_state.scan_mode, st.session_state.road_points, st.session_state.search_results = None, [], None
        st.session_state.pending_road = False
        st.session_state.pending_road_points = []
        st.session_state.pending_search_points = None
        if 'road_geometry' in st.session_state: del st.session_state['road_geometry']
        st.rerun()

# --- MAP RENDERING ---
m = folium.Map(location=st.session_state.center, zoom_start=st.session_state.zoom, tiles=None)
st.session_state.current_map = m
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
            icon = ''
            if bird.get('has_photo'):
                icon = 'camera'
            elif bird.get('has_comment'):
                icon = 'comment'

            popup_html = f"""
            <div style='font-family: Arial; width: 200px;'>
                <h4 style='margin-bottom:5px;'>{bird['comName']}</h4>
                <b>Date:</b> {bird['obsDt']}<br>
                <b>Location:</b> {bird['locName']}<br>
                <b>Count:</b> {bird.get('howMany', 'N/A')}<br>
                <a href='https://ebird.org/checklist/{bird['subId']}' target='_blank'>View Checklist</a></div>"""
            folium.Marker(
                location=[bird['lat'], bird['lng']],
                popup=folium.Popup(popup_html, max_width=250),
                tooltip=com_name,
                icon=folium.Icon(color=color, icon=icon, prefix='fa')
            ).add_to(fg)
        fg.add_to(m)
        lifer_groups[com_name] = fg

    overlay_tree = {
        "label": "Map Overlays",
        "children": [
            {
                "label": "Search Grid", 
                "layer": grid_group
            },
            {
                "label": "Potential Lifers",
                "select_all_checkbox": "Select/Unselect All",
                "children": [
                    {"label": name, "layer": group} 
                    for name, group in sorted(lifer_groups.items())
                ]
            }
        ]
    }
    
    TreeLayerControl(overlay_tree=overlay_tree, collapsed=False).add_to(m)
    spider.add_to(m)
    folium.FitOverlays().add_to(m)

map_data = st_folium(m, height=1000, use_container_width=True, key="mapper", wrap_longitude=True)

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
        elif st.session_state.scan_mode == 'single':
            search_points = [click]
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
            try:
                st.markdown("### 🛰️ Scanning...")
                progress_bar = st.progress(0)
                progress_text = st.empty()

                seen_species = get_seen_species(uploaded_csv, DEFAULT_LIFE_LIST)
                species_map = {}
                checklist_cache = {}

                total = len(search_points)

                for idx, (pt_lat, pt_lng) in enumerate(search_points):
                    obs = ebird.get_nearby_observations(
                        user_api_key,
                        pt_lat,
                        pt_lng,
                        dist=RADIUS,
                        back=BACK_DAYS,
                        category='species'
                    )

                    lifers = [
                        o for o in obs
                        if o['comName'] not in seen_species
                        and o.get('exoticCategory') != 'X'
                    ]

                    for sp in lifers:
                        s_code = sp['speciesCode']

                        specifics = ebird.get_nearest_species(
                            user_api_key,
                            s_code,
                            pt_lat,
                            pt_lng,
                            dist=RADIUS,
                            back=BACK_DAYS
                        )

                        if s_code not in species_map:
                            species_map[s_code] = []

                        for b in specifics:
                            # Avoid duplicates
                            if any(existing['subId'] == b['subId']
                                   for existing in species_map[s_code]):
                                continue

                            subid = b['subId']

                            # Fetch checklist only once per subId
                            if subid not in checklist_cache:
                                checklist_cache[subid] = fetch_checklist(
                                    user_api_key, subid
                                )

                            cl = checklist_cache[subid]

                            # Enrich bird with metadata
                            b['has_comment'] = False
                            b['has_photo'] = False

                            for o in cl.get('obs', []):
                                if o.get('speciesCode') == s_code:
                                    if o.get('comments'):
                                        b['has_comment'] = True

                                    if o.get('mediaCounts'):
                                        if o['mediaCounts'].get('P'):
                                            b['has_photo'] = True

                            species_map[s_code].append(b)

                    # Progress update
                    pct = int(((idx + 1) / total) * 100)
                    progress_bar.progress(pct)
                    progress_text.markdown(f"Scanned **{idx + 1}/{total}** sections")

                st.session_state.search_results = {'points': search_points, 'species_map': species_map}
                st.session_state.scan_mode, st.session_state.road_points = None, []
                st.rerun()

            except Exception as e:
                st.error(f"eBird API Error: {e}")

