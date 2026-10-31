import L from 'leaflet';
import { createElement } from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { riskIcon } from '../lib/riskIcons';
import { riskMeta } from '../lib/risk';

const cache = new Map<string, L.DivIcon>();

/** Risk-coloured disc with the level's icon, matching chips and the legend. */
export function checkpointIcon(risk: number | null, dimmed: boolean): L.DivIcon {
  const key = `${risk}-${dimmed}`;
  let icon = cache.get(key);
  if (!icon) {
    const meta = riskMeta(risk);
    const size = dimmed ? 14 : 22;
    const r = size / 2;
    const glyph = dimmed
      ? ''
      : renderToStaticMarkup(
          createElement(riskIcon(risk), {
            size: 14,
            x: r - 7,
            y: r - 7,
            color: meta.text,
            strokeWidth: 2.5,
          }),
        );
    icon = L.divIcon({
      className: 'marker-wrap',
      html: `<svg width="${size}" height="${size}" viewBox="0 0 ${size} ${size}" style="opacity:${dimmed ? 0.8 : 1}"><circle cx="${r}" cy="${r}" r="${r - 1}" fill="${meta.color}" stroke="#ffffff" stroke-width="2"/>${glyph}</svg>`,
      iconSize: [size, size],
      iconAnchor: [r, r],
      popupAnchor: [0, -r],
    });
    cache.set(key, icon);
  }
  return icon;
}

/** Teardrop pin with a letter; dark for the origin, primary blue for the destination. */
export function endpointIcon(letter: 'A' | 'B'): L.DivIcon {
  const fill = letter === 'A' ? '#0f172a' : '#1d4ed8';
  return L.divIcon({
    className: 'marker-wrap',
    html: `<svg width="28" height="38" viewBox="0 0 28 38"><path d="M14 37C14 37 2 22.5 2 14a12 12 0 0 1 24 0c0 8.5-12 23-12 23z" fill="${fill}" stroke="#ffffff" stroke-width="2"/><text x="14" y="18.5" text-anchor="middle" font-family="system-ui, sans-serif" font-size="12" font-weight="700" fill="#ffffff">${letter}</text></svg>`,
    iconSize: [28, 38],
    iconAnchor: [14, 37],
    popupAnchor: [0, -34],
  });
}
