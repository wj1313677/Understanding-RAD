/**
 * Generates the standardized HTML content for tooltips.
 */
export function generateTooltipHtml(point) {
    const fields = [
        { label: 'Latitude', key: 'FRA Point Latitude' },
        { label: 'Longitude', key: 'FRA Point Longitude' },
        { label: 'Change Status', key: 'Change Status' },
        { label: 'Point Type', key: 'Point Type' },
        { label: 'FRA Name', key: 'FRA Name' },
        { label: 'En-route', key: 'FRA Status En-Route' },
        { label: 'ARR/DEP', key: 'FRA Status ARR/DEP' },
        { label: 'Arrival Airport(s)', key: 'Arrival Airport(s)' },
        { label: 'Departure Airport(s)', key: 'Departure Airport(s)' },
        { label: 'FLOS', key: 'FLOS' },
        { label: 'Level Availability', key: 'Level Availability' },
        { label: 'Time Availability', key: 'Time Availability' },
        { label: 'Airspace Loc.', key: 'Airspace Location Indicators' },
        { label: 'Cross-Border States', key: 'Cross-Border FRA States' },
        { label: 'Remarks', key: 'Remarks' }
    ];

    const rows = fields.map(field => {
        const value = point[field.key] || '-';
        return `<div style="margin-bottom:2px">
            <span style="color:#aaa; font-weight:bold; margin-right: 5px;">${field.label}:</span>
            <span>${value}</span>
        </div>`;
    }).join('');

    return `
        <div style="font-family: sans-serif; font-size: 12px; line-height: 1.4;">
            <div style="font-weight: bold; font-size: 14px; margin-bottom: 8px; border-bottom: 1px solid #666; padding-bottom: 4px;">    
                ${point.name}
            </div>
            ${rows}
        </div>
    `;
}
