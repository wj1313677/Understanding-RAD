import React, { useEffect, useRef } from 'react';
import * as Cesium from 'cesium';
import 'cesium/Build/Cesium/Widgets/widgets.css';
import { getColorFromString, rgbToCss } from '../utils/colorUtils';
import { generateTooltipHtml } from '../utils/tooltipUtils';
import { getTriangleMarkerUrl } from '../utils/markerUtils';

const CesiumViewer = ({ data, theme, highlightedPoints }) => {
    const containerRef = useRef(null);
    const viewerRef = useRef(null);

    // Effect to handle theme changes
    useEffect(() => {
        if (!viewerRef.current) return;

        const viewer = viewerRef.current;
        const layers = viewer.imageryLayers;
        layers.removeAll();

        const mapUrl = theme === 'light'
            ? 'https://basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png'
            : 'https://basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png';

        layers.addImageryProvider(new Cesium.UrlTemplateImageryProvider({
            url: mapUrl
        }));

    }, [theme]); // Re-run when theme changes

    useEffect(() => {
        if (!containerRef.current) return;

        // Initialize viewer if not already done
        if (!viewerRef.current) {
            viewerRef.current = new Cesium.Viewer(containerRef.current, {
                terrainProvider: undefined,
                baseLayerPicker: false,
                geocoder: false,
                homeButton: false,
                sceneModePicker: false,
                navigationHelpButton: false,
                animation: false,
                timeline: false,
                fullscreenButton: false,
                imageryProvider: false, // We'll add it in the theme effect
            });

            // Remove default credits
            viewerRef.current.cesiumWidget.creditContainer.style.display = 'none';

            // Initial theme set handled by the theme effect above
        }

        const viewer = viewerRef.current;

        // Clear existing entities
        viewer.entities.removeAll();

        // Cache for generated triangle images based on color keys
        const triangleCache = {};

        const getTriangleCanvas = (fillRgb, borderRgb) => {
            const key = `${fillRgb.join(',')}-${borderRgb.join(',')}`;
            if (triangleCache[key]) return triangleCache[key];

            const size = 32;
            const canvas = document.createElement('canvas');
            canvas.width = size;
            canvas.height = size;
            const ctx = canvas.getContext('2d');

            // Draw larger triangle (Border)
            ctx.beginPath();
            ctx.moveTo(size / 2, 0);
            ctx.lineTo(size, size);
            ctx.lineTo(0, size);
            ctx.closePath();
            ctx.fillStyle = `rgb(${borderRgb.join(',')})`;
            ctx.fill();

            // Draw smaller triangle (Fill)
            // Scale down significantly to create thick border
            // Border thickness determined by difference between outer and inner
            const inset = 6; // Increased from ~2-3 to 6 for wider border
            ctx.beginPath();
            ctx.moveTo(size / 2, inset * 1.5); // Top
            ctx.lineTo(size - inset, size - inset); // Bottom Right
            ctx.lineTo(inset, size - inset); // Bottom Left
            ctx.closePath();

            ctx.fillStyle = `rgb(${fillRgb.join(',')})`;
            ctx.fill();

            triangleCache[key] = canvas;
            return canvas;
        };

        // Add points
        if (data && data.length > 0) {
            data.forEach(point => {
                const fillColorRgb = getColorFromString(point.airspaceLocation || 'Unknown');

                const borderKey = (point.crossBorderStates && point.crossBorderStates.trim())
                    ? point.crossBorderStates
                    : (point.airspaceLocation || 'Unknown');
                const borderColorRgb = getColorFromString(borderKey);

                const tooltipHtml = generateTooltipHtml(point);

                const markerCanvas = getTriangleCanvas(fillColorRgb, borderColorRgb);

                viewer.entities.add({
                    name: point.name, // Important for lookups
                    position: Cesium.Cartesian3.fromDegrees(point.coordinates[0], point.coordinates[1]),
                    billboard: {
                        image: markerCanvas, // Use the generated canvas directly
                        scale: 1.0,
                        horizontalOrigin: Cesium.HorizontalOrigin.CENTER,
                        verticalOrigin: Cesium.VerticalOrigin.CENTER
                    },
                    label: {
                        text: point.name,
                        font: '10px sans-serif',
                        style: Cesium.LabelStyle.FILL_AND_OUTLINE,
                        outlineWidth: 2,
                        verticalOrigin: Cesium.VerticalOrigin.BOTTOM,
                        pixelOffset: new Cesium.Cartesian2(0, -9),
                        distanceDisplayCondition: new Cesium.DistanceDisplayCondition(0, 500000)
                    },
                    description: tooltipHtml
                });
            });

            viewer.zoomTo(viewer.entities);
        }

        return () => {
            if (viewerRef.current) {
                viewerRef.current.destroy();
                viewerRef.current = null;
            }
        };
    }, [data]); // Re-run when data changes

    // Effect to handle highlighting (dimming others)
    useEffect(() => {
        if (!viewerRef.current) return;

        const entities = viewerRef.current.entities.values;
        // If highlightedPoints is null/empty -> RESET all to normal
        const isFiltering = highlightedPoints && highlightedPoints.size > 0;

        for (let i = 0; i < entities.length; i++) {
            const entity = entities[i];
            const name = entity.label?.text; // Use entity.label.text for the name

            // Note: In Cesium entities, we can't easily change the "image" back and forth efficiently without regenerating canvas
            // OR we can use the 'color' property of billboard to tint/fade.
            // Setting color to white (default) uses original image.
            // Setting color to Color(1,1,1, 0.1) creates transparency.

            if (isFiltering) {
                if (highlightedPoints.has(name)) {
                    entity.billboard.color = Cesium.Color.WHITE; // Full opacity
                    entity.billboard.scale = 1.0; // Normal Size
                    // Ensure it's on top?
                } else {
                    entity.billboard.color = new Cesium.Color(1.0, 1.0, 1.0, 0.05); // Very faint
                    entity.billboard.scale = 0.5; // Shrink
                }
            } else {
                // Reset
                entity.billboard.color = Cesium.Color.WHITE;
                entity.billboard.scale = 1.0;
            }
        }

        if (isFiltering) {
            viewerRef.current.scene.requestRender();
        }

    }, [highlightedPoints]);

    return (
        <div ref={containerRef} style={{ width: '100%', height: '100%' }} />
    );
};

export default CesiumViewer;
