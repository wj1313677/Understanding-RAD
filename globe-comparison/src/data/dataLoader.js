import Papa from 'papaparse';
import { parseCoordinate } from '../utils/coordinateParser';

export const loadFRAData = async () => {
    try {
        const response = await fetch('/FRA_Points.csv');
        const csvText = await response.text();

        return new Promise((resolve, reject) => {
            Papa.parse(csvText, {
                header: true,
                skipEmptyLines: true,
                complete: (results) => {
                    const parsedData = results.data.map(row => {
                        // Coordinates are now in "FRA Point Latitude" / "FRA Point Longitude"
                        // But need parsing from DMS string (e.g. N500424) to decimal.
                        // Implemented inline or via helper? 
                        // Let's implement a robust inline parser or update utils.
                        // The user provided python logic: 
                        // direction = str[0], deg=val[:2/3], min=val[2/3:4/5], sec=val[4/5:]

                        const parseDMS = (coordStr) => {
                            if (!coordStr) return null;
                            const direction = coordStr[0];
                            const val = coordStr.slice(1);

                            let deg, min, sec;
                            if (direction === 'N' || direction === 'S') {
                                deg = parseInt(val.slice(0, 2), 10);
                                min = parseInt(val.slice(2, 4), 10);
                                sec = parseInt(val.slice(4), 10);
                            } else {
                                deg = parseInt(val.slice(0, 3), 10);
                                min = parseInt(val.slice(3, 5), 10);
                                sec = parseInt(val.slice(5), 10);
                            }

                            let decimal = deg + min / 60 + sec / 3600;
                            if (direction === 'S' || direction === 'W') {
                                decimal *= -1;
                            }
                            return decimal;
                        };

                        const lat = parseDMS(row['FRA Point Latitude']);
                        const lon = parseDMS(row['FRA Point Longitude']);

                        if (!isNaN(lat) && !isNaN(lon)) {
                            return {
                                ...row,
                                coordinates: [lon, lat],
                                name: row['FRA Point'],
                                type: row['Point Type'],
                                airspaceLocation: row['Airspace Location Indicators'],
                                crossBorderStates: row['Cross-Border FRA States']
                            };
                        }
                        return null;
                    }).filter(item => item !== null);

                    resolve(parsedData);
                },
                error: (err) => {
                    reject(err);
                }
            });
        });
    } catch (error) {
        console.error("Error loading CSV:", error);
        return [];
    }
};
