import React from 'react';
import DeckGL from '@deck.gl/react';
import { IconLayer } from '@deck.gl/layers';
import { TileLayer } from '@deck.gl/geo-layers';
import { BitmapLayer } from '@deck.gl/layers';
import { _GlobeView as GlobeView } from '@deck.gl/core';
import { getColorFromString } from '../utils/colorUtils';
import { generateTooltipHtml } from '../utils/tooltipUtils';
import { getTriangleMarkerUrl } from '../utils/markerUtils';

const INITIAL_VIEW_STATE = {
    longitude: 10,
    latitude: 45,
    zoom: 2,
    pitch: 0,
    bearing: 0
};

const DeckGLViewer = ({ data, theme, highlightedPoints }) => {
    const triangleUrl = getTriangleMarkerUrl();
    const mapStyle = theme === 'light'
        ? 'https://basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png'
        : 'https://basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png';

    // Helper for dimming
    const getDimmedColor = (rgbArray) => {
        // If highlightedPoints is null, everyone is active (return original RGB)
        // If highlightedPoints is Set, check membership.
        // But `d` is not passed here. This helper must be called inside the accessor.
        return rgbArray;
    };

    const isDimmed = (pointName) => {
        if (!highlightedPoints) return false; // No filter active
        return !highlightedPoints.has(pointName); // Dim if NOT in matches
    };

    const layers = [
        // Base Map Layer
        new TileLayer({
            // ... (keep same)
            id: 'base-map',
            data: mapStyle,
            minZoom: 0,
            maxZoom: 19,
            tileSize: 256,
            renderSubLayers: props => {
                const {
                    bbox: { west, south, east, north }
                } = props.tile;

                return new BitmapLayer(props, {
                    data: null,
                    image: props.data,
                    bounds: [west, south, east, north]
                });
            }
        }),
        // Data Layer - Border (Background)
        new IconLayer({
            id: 'fra-points-border',
            data: data,
            pickable: false, // Only top layer needs to pick
            iconAtlas: triangleUrl,
            iconMapping: {
                marker: { x: 0, y: 0, width: 64, height: 64, mask: true }
            },
            getIcon: d => 'marker',
            // Slightly larger scale for border
            sizeScale: 20, // Increased from 15
            getPosition: d => d.coordinates,
            getColor: d => {
                // If dimmed, use very low opacity or grey
                if (isDimmed(d.name)) return [100, 100, 100, 20]; // Faint grey

                // Normal logic
                if (d.crossBorderStates) { // Prioritize Cross-Border
                    // Hash string to color? Or Fixed color?
                    // Previous logic: hash string
                    return getColorFromString(d.crossBorderStates);
                }
                // Fallback to Airspace Location for border if not cross-border?
                // Or user requested specifically cross border states tinting the border.
                // Re-using the logic from previous session:
                if (d.airspaceLocation) return getColorFromString(d.airspaceLocation);

                return [255, 255, 255];
            },
            updateTriggers: {
                getColor: [highlightedPoints]
            }
        }),
        // Data Layer - Fill (Foreground)
        new IconLayer({
            id: 'fra-points-fill',
            data: data,
            pickable: true,
            iconAtlas: triangleUrl,
            iconMapping: {
                marker: { x: 0, y: 0, width: 64, height: 64, mask: true }
            },
            getIcon: d => 'marker',
            // Smaller scale for fill to create wider border effect
            sizeScale: 10, // Decreased from 11
            getPosition: d => d.coordinates,
            getColor: d => {
                if (isDimmed(d.name)) return [100, 100, 100, 20]; // Faint

                if (d.airspaceLocation) {
                    return getColorFromString(d.airspaceLocation);
                }
                return [0, 128, 255];
            },
            updateTriggers: {
                getColor: [highlightedPoints]
            },
            getTooltip: ({ object }) => object && generateTooltipHtml(object)
        })
    ];

    return (
        <DeckGL
            initialViewState={INITIAL_VIEW_STATE}
            controller={true}
            layers={layers}
            views={new GlobeView()}
            getTooltip={({ object }) => {
                if (!object) return null;
                return {
                    html: generateTooltipHtml(object),
                    style: {
                        backgroundColor: '#222',
                        color: '#fff',
                        fontSize: '12px',
                        padding: '10px',
                        maxWidth: '300px',
                        zIndex: 1000
                    }
                };
            }}
        />
    );
};

export default DeckGLViewer;
