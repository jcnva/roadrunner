# Roadrunner
A trip planning app for lifer-chasers.
Find "lifers" by cross-referencing your personal eBird "Life List" with real-time observation data.
Search for the most recent sightings within a specified area up to 136km in diameter, or along a cross-county road trip route, over the past 30 days.

## Requirements

* eBird API Key
 * Get your free API key from the eBird developer portal:
  1. Log in to eBird
  2. Visit: https://ebird.org/api/keygen

* OpenRouteService API Key
 * Required for Road Trip Routing.
 * Get a free OpenRouteService key:
  1. Create an account at https://openrouteservice.org
  2. Go to Dashboard → API Keys
  3. Create a new token

* eBird Life List
  1. Log in to eBird
  2. Go to My eBird → Sightings List
  3. Click “Download Data”
    
## Filtering

* Automatic Exclusion: The app compares nearby sightings against your life list.
 * 💡Tip: You can include a species in your search by simply deleting its row from the CSV file.
* Exotic Filtering: It ignores species categorized as exotic escapees (category 'X'), hybrids, slashes, and spuhs to prioritize native or established sightings.

## Search Modes

The app offers three ways to scan the globe for birds:

* 📍 Single Scan:
  * The user clicks a single point on the map.
  * The app searches a single circle around that point.
  * Use Case: Searching a circular area up to 50km in radius.

* 🎯 Hex Scan:
  * The user clicks a single point on the map.
  * The app generates a hexagonal grid of coordinates around that point with an array of circles.
  * Use Case: Searching a broader area up to 136km in radius.

* 🚗 Road Trip:
  * The user selects a START and an END point.
  * The app uses the OpenRouteService API to calculate the actual driving route.
  * Use Case: Planning a trip and scanning for birds within 50km from the road.

## Results

* Color-coded markers show where the birds are located, with icons to indicate sightings with photos or comments.
* 💾 Save results as HTML files to browse offline, or share with others.
  * 💡Tip: If app performance struggles with larger reports, browse the saved HTML map for a smoother user experience.
