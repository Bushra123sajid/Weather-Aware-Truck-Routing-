/** Route colours avoid the risk palette; dash patterns give a second, non-colour cue. */
export const ROUTE_STYLES = [
  { color: '#1d4ed8', dashArray: undefined, pattern: 'solid' },
  { color: '#0e7490', dashArray: '12 8', pattern: 'dashed' },
  { color: '#334155', dashArray: '2 8', pattern: 'dotted' },
] as const;

export function routeStyle(index: number) {
  return ROUTE_STYLES[index % ROUTE_STYLES.length];
}
