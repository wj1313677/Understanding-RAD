let triangleDataUrl = null;

/**
 * Creates a white triangle image and returns it as a Data URL.
 * It's memoized so we don't recreate it constantly.
 * Useful for Deck.gl IconLayer (mask: true) and Cesium Billboard (color tinting).
 */
export function getTriangleMarkerUrl() {
    if (triangleDataUrl) return triangleDataUrl;

    const size = 64; // High res for crispness
    const canvas = document.createElement('canvas');
    canvas.width = size;
    canvas.height = size;
    const ctx = canvas.getContext('2d');

    // Draw Triangle
    ctx.beginPath();
    ctx.moveTo(size / 2, 0);       // Top Center
    ctx.lineTo(size, size);        // Bottom Right
    ctx.lineTo(0, size);           // Bottom Left
    ctx.closePath();

    ctx.fillStyle = 'white';
    ctx.fill();

    triangleDataUrl = canvas.toDataURL();
    return triangleDataUrl;
}
