import { useEffect, useRef } from 'react';
import { useMap } from 'react-leaflet';
import { RiskHeatLayer, type HeatCell } from './RiskHeatLayer';

interface Props {
  cells: HeatCell[];
  spacingMi: number;
  visible: boolean;
}

/** React bridge: the Leaflet layer is created once; data changes only trigger a canvas redraw. */
export function HeatLayer({ cells, spacingMi, visible }: Props) {
  const map = useMap();
  const layerRef = useRef<RiskHeatLayer | null>(null);

  useEffect(() => {
    const layer = new RiskHeatLayer();
    layerRef.current = layer;
    return () => {
      layer.remove();
      layerRef.current = null;
    };
  }, []);

  useEffect(() => {
    const layer = layerRef.current;
    if (!layer) return;
    if (visible && !map.hasLayer(layer)) layer.addTo(map);
    if (!visible && map.hasLayer(layer)) layer.remove();
  }, [map, visible]);

  useEffect(() => {
    layerRef.current?.setCells(cells, spacingMi);
  }, [cells, spacingMi]);

  return null;
}
