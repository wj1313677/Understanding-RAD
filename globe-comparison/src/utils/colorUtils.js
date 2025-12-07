/**
 * Generates a consistent RGB color array from a string.
 * Returns [r, g, b]
 */
export function getColorFromString(str) {
    if (!str) return [200, 200, 200]; // Default grey

    let hash = 0;
    for (let i = 0; i < str.length; i++) {
        hash = str.charCodeAt(i) + ((hash << 5) - hash);
    }

    const c = (hash & 0x00FFFFFF)
        .toString(16)
        .toUpperCase();

    const hex = "00000".substring(0, 6 - c.length) + c;

    const r = parseInt(hex.substring(0, 2), 16);
    const g = parseInt(hex.substring(2, 4), 16);
    const b = parseInt(hex.substring(4, 6), 16);

    return [r, g, b];
}

/**
 * Helper to convert RGB array to CSS string.
 */
export function rgbToCss(rgb) {
    return `rgb(${rgb[0]}, ${rgb[1]}, ${rgb[2]})`;
}
