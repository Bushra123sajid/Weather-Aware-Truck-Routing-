export type LatLngTuple = [number, number];

/** Decode a Google encoded polyline (precision 5 by default) into [lat, lng] pairs. */
export function decodePolyline(encoded: string, precision = 5): LatLngTuple[] {
  const factor = 10 ** precision;
  const out: LatLngTuple[] = [];
  let index = 0;
  let lat = 0;
  let lng = 0;
  while (index < encoded.length) {
    for (let k = 0; k < 2; k++) {
      let shift = 0;
      let result = 0;
      let byte: number;
      do {
        byte = encoded.charCodeAt(index++) - 63;
        result |= (byte & 0x1f) << shift;
        shift += 5;
      } while (byte >= 0x20); // charCodeAt past the end is NaN, which also ends the loop
      const delta = result & 1 ? ~(result >> 1) : result >> 1;
      if (k === 0) lat += delta;
      else lng += delta;
    }
    out.push([lat / factor, lng / factor]);
  }
  return out;
}
