/**
 * Parses a coordinate string like "N404519" or "E0183830" into decimal degrees.
 * Format seems to be [Direction][DD][MM][SS] (Degrees, Minutes, Seconds).
 * 
 * Examples: 
 * N404519 -> 40 + 45/60 + 19/3600 = 40.75527
 * E0183830 -> 18 + 38/60 + 30/3600 = 18.64166
 */
export function parseCoordinate(coordStr) {
    if (!coordStr) return null;

    // Trim whitespace
    const s = coordStr.trim();
    if (s.length < 5) return null; // Too short to be valid

    const direction = s[0];
    const isLat = (direction === 'N' || direction === 'S');
    const isLon = (direction === 'E' || direction === 'W');

    if (!isLat && !isLon) return parseFloat(s); // Maybe already decimal?

    let degrees, minutes, seconds;

    // Latitude usually 2 digits for degrees: N DD MM SS
    // Longitude usually 3 digits for degrees: E DDD MM SS

    // However, looking at example E0183830 (8 chars) -> E 018 38 30
    // N404519 (7 chars) -> N 40 45 19

    try {
        if (isLat) {
            degrees = parseInt(s.substring(1, 3), 10);
            minutes = parseInt(s.substring(3, 5), 10);
            seconds = parseInt(s.substring(5, 7), 10);
        } else {
            // Longitude
            degrees = parseInt(s.substring(1, 4), 10);
            minutes = parseInt(s.substring(4, 6), 10);
            seconds = parseInt(s.substring(6, 8), 10);
        }

        let decimal = degrees + minutes / 60 + seconds / 3600;

        if (direction === 'S' || direction === 'W') {
            decimal *= -1;
        }

        return decimal;
    } catch (e) {
        console.error("Error parsing coordinate:", coordStr, e);
        return null;
    }
}
