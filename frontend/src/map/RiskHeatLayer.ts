import L from 'leaflet';
import { riskMeta } from '../lib/risk';

export interface HeatCell {
  lat: number;
  lng: number;
  level: number | null;
}

const MILES_PER_DEG_LAT = 69.055;
// Low cells are drawn fainter so hazards stand out.
const LEVEL_ALPHA: Record<number, number> = { 1: 0.35, 2: 0.6, 3: 0.7, 4: 0.8, 5: 0.85 };

/**
 * A single <canvas> overlay that paints one square per corridor grid cell, coloured by
 * risk level, then softens it with a CSS blur so it reads as a heatmap.
 *
 * Why custom instead of leaflet.heat: leaflet.heat blends by point *density*, but we
 * need discrete risk colours. Redrawing ~250 rects is well under 1 ms, so the slider
 * can update every frame without touching React or the rest of the map.
 */
export class RiskHeatLayer extends L.Layer {
  private canvas: HTMLCanvasElement | null = null;
  private cells: HeatCell[] = [];
  private spacingMi = 10;
  private refLat = 0;
  private raf = 0;

  setCells(cells: HeatCell[], spacingMi: number): this {
    this.cells = cells;
    this.spacingMi = spacingMi || 10;
    if (cells.length) this.refLat = cells.reduce((s, c) => s + c.lat, 0) / cells.length;
    this.scheduleDraw();
    return this;
  }

  onAdd(map: L.Map): this {
    this.canvas = L.DomUtil.create('canvas', 'risk-heat-layer leaflet-zoom-hide');
    this.canvas.setAttribute('aria-hidden', 'true');
    map.getPanes().overlayPane.appendChild(this.canvas);
    map.on('moveend zoomend resize viewreset', this.reset, this);
    this.reset();
    return this;
  }

  onRemove(map: L.Map): this {
    map.off('moveend zoomend resize viewreset', this.reset, this);
    cancelAnimationFrame(this.raf);
    this.canvas?.remove();
    this.canvas = null;
    return this;
  }

  private reset(): void {
    const map = this._map;
    if (!map || !this.canvas) return;
    const size = map.getSize();
    const dpr = window.devicePixelRatio || 1;
    this.canvas.width = Math.round(size.x * dpr);
    this.canvas.height = Math.round(size.y * dpr);
    this.canvas.style.width = `${size.x}px`;
    this.canvas.style.height = `${size.y}px`;
    L.DomUtil.setPosition(this.canvas, map.containerPointToLayerPoint([0, 0]));
    this.draw();
  }

  private scheduleDraw(): void {
    cancelAnimationFrame(this.raf);
    this.raf = requestAnimationFrame(() => this.draw());
  }

  private draw(): void {
    const map = this._map;
    const canvas = this.canvas;
    if (!map || !canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;
    const dpr = window.devicePixelRatio || 1;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    if (!this.cells.length) return;

    // Cell size in pixels at the current zoom (grid spacing is in miles).
    const dLat = this.spacingMi / MILES_PER_DEG_LAT;
    const dLng = dLat / Math.max(Math.cos((this.refLat * Math.PI) / 180), 0.01);
    const p0 = map.latLngToContainerPoint([this.refLat, 0]);
    const p1 = map.latLngToContainerPoint([this.refLat + dLat, dLng]);
    const w = Math.abs(p1.x - p0.x) * 1.05;
    const h = Math.abs(p1.y - p0.y) * 1.05;
    canvas.style.filter = `blur(${Math.max(2, Math.min(w, h) * 0.35).toFixed(1)}px)`;

    const size = map.getSize();
    for (const cell of this.cells) {
      if (cell.level == null) continue;
      const pt = map.latLngToContainerPoint([cell.lat, cell.lng]);
      if (pt.x < -w || pt.y < -h || pt.x > size.x + w || pt.y > size.y + h) continue;
      ctx.globalAlpha = LEVEL_ALPHA[cell.level] ?? 0.6;
      ctx.fillStyle = riskMeta(cell.level).color;
      ctx.fillRect(pt.x - w / 2, pt.y - h / 2, w, h);
    }
    ctx.globalAlpha = 1;
  }
}
