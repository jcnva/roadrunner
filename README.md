# Roadrunner
A trip planning app for lifer-chasers. Its primary purpose is to help users find "lifers" (bird species they have never seen before) by cross-referencing their personal eBird "Life List" with real-time observation data from the eBird API.

## Core Functionality
### Filtering

The app doesn't just show birds; it filters them based on your personal history.

* Life List Integration: Users can upload their eBird sightings as a CSV.
* Automatic Exclusion: The app compares nearby sightings against this list and only displays species the user hasn't checked off yet.
* Exotic Filtering: It ignores species categorized as exotic (category 'X') to prioritize native or established sightings.

### Search Modes

The app offers two distinct ways to scan the globe for birds:

* 🎯 Hex Scan:
  * How it works: The user clicks a single point on the map.
  * Logic: The app generates a hexagonal grid of coordinates around that point with an array of 50km diameter circles.
  * Use Case: Searching a broad area with a 136km radius.

* 🚗 Road Trip:
  * How it works: The user selects a START and END point.
  * Logic: It uses the OpenRouteService API to calculate the actual driving route and samples coordinates every ~70km along that road.
  * Use Case: Planning a trip and identifying which rare birds can be found within a 50km detour of the highway.
