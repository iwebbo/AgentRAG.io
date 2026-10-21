### 3. Travel Expert Agent

**Purpose**: Creation of personalized travel itineraries, logistical management of reservations (flights, accommodations), and provision of real-time local information.

**Workflow**:
1. Collect user preferences (destination, dates, budget, interests).
2. Query external APIs to retrieve data (flights, hotels, attractions).
3. Optimize the itinerary according to constraints (travel time, cost, thematic interest).
4. Generate a detailed plan and activity suggestions.
5. Propose alternatives or adjust the trip based on requested changes.

**Configuration**:
```json
{
  "api_keys": ["flight_booking", "hotel_reservation", "local_attractions"],
  "preferred_regions": ["Europe", "Asia", "North America"],
  "budget_levels": ["low", "medium", "luxury"],
  "travel_styles": ["adventure", "family", "business", "cultural"]
}
```

**Use Cases**:
- Creation of a multi-city itinerary over 10 days.
- Search for flights and hotels optimized for a given budget.
- Suggestion of local activities based on interests (e.g., gastronomy, history).
- Management of last-minute changes or cancellations.