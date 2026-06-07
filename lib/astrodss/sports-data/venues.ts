export type VenueCoordinate = {
  latitude: number;
  longitude: number;
};

export const KNOWN_VENUE_COORDINATES: Record<string, VenueCoordinate> = {
  "Angel Stadium": { latitude: 33.8003, longitude: -117.8827 },
  "Busch Stadium": { latitude: 38.6226, longitude: -90.1928 },
  "Camden Yards": { latitude: 39.2839, longitude: -76.6217 },
  "Chase Field": { latitude: 33.4455, longitude: -112.0667 },
  "Citi Field": { latitude: 40.7571, longitude: -73.8458 },
  "Citizens Bank Park": { latitude: 39.9061, longitude: -75.1665 },
  "Comerica Park": { latitude: 42.339, longitude: -83.0485 },
  "Coors Field": { latitude: 39.7559, longitude: -104.9942 },
  "Dodger Stadium": { latitude: 34.0739, longitude: -118.24 },
  "Fenway Park": { latitude: 42.3467, longitude: -71.0972 },
  "Globe Life Field": { latitude: 32.7473, longitude: -97.0842 },
  "Great American Ball Park": { latitude: 39.0979, longitude: -84.5082 },
  "Kauffman Stadium": { latitude: 39.0517, longitude: -94.4803 },
  "loanDepot park": { latitude: 25.7781, longitude: -80.2197 },
  "Minute Maid Park": { latitude: 29.7572, longitude: -95.3555 },
  "Nationals Park": { latitude: 38.873, longitude: -77.0074 },
  "Oracle Park": { latitude: 37.7786, longitude: -122.3893 },
  "PNC Park": { latitude: 40.4469, longitude: -80.0057 },
  "Progressive Field": { latitude: 41.4962, longitude: -81.6852 },
  "Rogers Centre": { latitude: 43.6414, longitude: -79.3894 },
  "T-Mobile Park": { latitude: 47.5914, longitude: -122.3325 },
  "Target Field": { latitude: 44.9817, longitude: -93.2776 },
  "Tropicana Field": { latitude: 27.7682, longitude: -82.6534 },
  "Truist Park": { latitude: 33.8907, longitude: -84.4677 },
  "Wrigley Field": { latitude: 41.9484, longitude: -87.6553 },
  "Yankee Stadium": { latitude: 40.8296, longitude: -73.9262 },
};

export function findVenueCoordinates(venue?: string): VenueCoordinate | undefined {
  if (!venue) return undefined;
  const exact = KNOWN_VENUE_COORDINATES[venue];
  if (exact) return exact;

  const lowerVenue = venue.toLowerCase();
  const match = Object.entries(KNOWN_VENUE_COORDINATES).find(([name]) => lowerVenue.includes(name.toLowerCase()));
  return match?.[1];
}
