# Roadrunner
A trip planning app for lifer-chasers.
Find "lifers" by cross-referencing your personal eBird "Life List" with real-time observation data.
Search for the most recent sightings within a specified area up to 136km in diameter, or along a cross-county road trip route, over the past 30 days.

## Filtering

The app doesn't just show birds; it filters them based on your personal history.

* Life List Integration: Users can upload their eBird sightings as a CSV.
* Automatic Exclusion: The app compares nearby sightings against this list and only displays species the user hasn't checked off yet.
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
