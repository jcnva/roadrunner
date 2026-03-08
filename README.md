# Roadrunner
A trip planning app for lifer-chasers.
Find "lifers" by cross-referencing your personal eBird "Life List" with real-time observation data.
Search for the most recent sightings of the past 30 days, within a specified area up to 136km in radius, or along a cross-county road trip route.

## Requirements

### eBird API Key
 * Get your free API key from the eBird developer portal:
  1. Log in to eBird
  2. Visit: https://ebird.org/api/keygen

### OpenRouteService API Key
 * Required for Road Trip Routing.
 * Get a free OpenRouteService key:
  1. Create an account at https://openrouteservice.org
  2. Go to Dashboard → API Keys
  3. Create a new token

### eBird Life List in .CSV format
 * If no file is provided, all birds will be reported. (⚠️Warning: VERY slow. Not recommended)
  1. Log in to eBird
  2. Go to My eBird → Sightings List
  3. Click “Download Data”
    
## Exclusions

* The app excludes all species in your life list from its search.
  * 💡Tip: You can include a species in your search by deleting its row from the CSV file.
* The app excludes birds categorized as exotic escapees (category 'X'), hybrids, slashes, and spuhs to prioritize native or established sightings.

## Search Modes

The app offers three ways to scan the globe for birds:

* 📍 Single Scan:
  * Click a single point on the map.
  * The app searches a single circle around that point.
  * Use Case: Searching a circular area up to a 50km radius.

* 🎯 Hex Scan:
  * Click a single point on the map.
  * The app generates a hexagonal grid of coordinates around that point with an array of circles.
  * Use Case: Searching a broader area up to a 136km radius.

* 🚗 Road Trip:
  * Click a START point, then an END point.
  * The app uses the OpenRouteService API to calculate the actual driving route.
  * Use Case: Planning a trip and scanning for birds within 50km from the road.

## Results

* Map Markers show where the birds are located.
  * Markers are color-coded by species.
  * Icons indicate sightings with photos or comments.
  * Click on a marker for sighting details and a link to the eBird checklist.
* 💾 Save results as an interactive HTML file to browse offline, or share with others.
  * 💡Tip: If app performance struggles with larger reports, try either (a) setting the map to Full Screen, or (b) browsing the saved HTML map, for a smoother user experience.
  * 💡Tip: If markers are not visible when you first open the HTML, try zooming ALL the way out.

## Demo

https://github.com/user-attachments/assets/7ed078e3-7445-4669-bb7a-4f9bb7c10928
