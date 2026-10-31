import { memo, useEffect, useMemo } from 'react';
import { MapContainer, Marker, Polyline, Popup, TileLayer, useMap } from 'react-leaflet';
import L from 'leaflet';
import type { PlanResponse, PlannedRoute } from '../api/types';
import { formatDateTime } from '../lib/format';
import { decodePolyline, type LatLngTuple } from '../lib/polyline';
import { riskMeta } from '../lib/risk';
import { routeStyle } from '../lib/routeStyle';
import { checkpointIcon, endpointIcon } from './icons';
import { HeatLayer } from './HeatLayer';
import { CheckpointPopup, RoutePopup } from './Popups';
import type { HeatCell } from './RiskHeatLayer';

interface Props {
  plan: PlanResponse | undefined;
  selectedId: string | null;
  onSelect: (id: string) => void;
  showAllCheckpoints: boolean;
  heat: { cells: HeatCell[]; spacingMi: number; visible: boolean };
}

const US_CENTER: LatLngTuple = [39.5, -98.35];

function FitBounds({ bounds }: { bounds: L.LatLngBounds | null }) {
  const map = useMap();
  useEffect(() => {
    if (bounds?.isValid()) map.fitBounds(bounds, { padding: [40, 40] });
  }, [map, bounds]);
  return null;
}

const RouteLayer = memo(function RouteLayer({
  route,
  index,
  coords,
  selected,
  anySelected,
  onSelect,
}: {
  route: PlannedRoute;
  index: number;
  coords: LatLngTuple[];
  selected: boolean;
  anySelected: boolean;
  onSelect: (id: string) => void;
}) {
  const style = routeStyle(index);
  const handlers = useMemo(() => ({ click: () => onSelect(route.id) }), [onSelect, route.id]);
  return (
    <>
      {/* Transparent wide line so thin routes are easy to click or tap. */}
      <Polyline
        positions={coords}
        pathOptions={{ weight: 18, opacity: 0 }}
        eventHandlers={handlers}
      />
      <Polyline
        positions={coords}
        eventHandlers={handlers}
        pathOptions={{
          color: style.color,
          weight: selected ? 7 : 4,
          opacity: selected || !anySelected ? 0.95 : 0.4,
          dashArray: style.dashArray,
          lineCap: 'round',
        }}
      >
        <Popup>
          <RoutePopup route={route} />
        </Popup>
      </Polyline>
    </>
  );
});

const CheckpointLayer = memo(function CheckpointLayer({
  route,
  dimmed,
}: {
  route: PlannedRoute;
  dimmed: boolean;
}) {
  return (
    <>
      {route.checkpoints.map((cp) => (
        <Marker
          key={`${route.id}-${cp.index}`}
          position={[cp.lat, cp.lng]}
          icon={checkpointIcon(cp.risk, dimmed)}
          zIndexOffset={dimmed ? 0 : 500 + (cp.risk ?? 0) * 10}
          keyboard={!dimmed}
          title={`${route.name} mile ${cp.mile.toFixed(0)}: ${riskMeta(cp.risk).label}`}
        >
          <Popup>
            <CheckpointPopup cp={cp} routeName={route.name} />
          </Popup>
        </Marker>
      ))}
    </>
  );
});

export const MapView = memo(function MapView({
  plan,
  selectedId,
  onSelect,
  showAllCheckpoints,
  heat,
}: Props) {
  const decoded = useMemo(
    () => (plan ? plan.routes.map((r) => decodePolyline(r.geometry)) : []),
    [plan],
  );
  const bounds = useMemo(() => {
    const all = decoded.flat();
    return all.length ? L.latLngBounds(all) : null;
  }, [decoded]);

  // Selected route last so it draws on top.
  const order = useMemo(() => {
    if (!plan) return [];
    const idx = plan.routes.map((_, i) => i);
    return idx.sort(
      (a, b) => Number(plan.routes[a].id === selectedId) - Number(plan.routes[b].id === selectedId),
    );
  }, [plan, selectedId]);

  return (
    <MapContainer center={US_CENTER} zoom={4} className="map" preferCanvas={false} worldCopyJump>
      <TileLayer
        attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
        url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
        maxZoom={18}
      />
      <HeatLayer cells={heat.cells} spacingMi={heat.spacingMi} visible={heat.visible} />
      {plan &&
        order.map((i) => (
          <RouteLayer
            key={plan.routes[i].id}
            route={plan.routes[i]}
            index={i}
            coords={decoded[i]}
            selected={plan.routes[i].id === selectedId}
            anySelected={selectedId != null}
            onSelect={onSelect}
          />
        ))}
      {plan &&
        plan.routes.map((r) =>
          r.id === selectedId || showAllCheckpoints ? (
            <CheckpointLayer key={r.id} route={r} dimmed={r.id !== selectedId} />
          ) : null,
        )}
      {plan && (
        <>
          <Marker
            position={[plan.origin.lat, plan.origin.lng]}
            icon={endpointIcon('A')}
            title="Origin"
          >
            <Popup>
              <strong>Origin</strong>
              <div>{plan.origin.label}</div>
              <div>Departs {formatDateTime(plan.departure_time)}</div>
            </Popup>
          </Marker>
          <Marker
            position={[plan.destination.lat, plan.destination.lng]}
            icon={endpointIcon('B')}
            title="Destination"
          >
            <Popup>
              <strong>Destination</strong>
              <div>{plan.destination.label}</div>
            </Popup>
          </Marker>
        </>
      )}
      <FitBounds bounds={bounds} />
    </MapContainer>
  );
});
