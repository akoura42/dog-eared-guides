// Shared Google Maps JS loader for client scripts. Safe to call from
// multiple components on one page — the script loads once.
let loading: Promise<any> | null = null;

export function ensureGoogleMaps(key: string): Promise<any> {
  const w = window as any;
  if (w.google?.maps) return Promise.resolve(w.google.maps);
  if (!loading) {
    loading = new Promise((resolve, reject) => {
      w.__degMapsReady = () => resolve(w.google.maps);
      const s = document.createElement('script');
      s.src = `https://maps.googleapis.com/maps/api/js?key=${encodeURIComponent(
        key
      )}&v=weekly&loading=async&callback=__degMapsReady`;
      s.onerror = () => reject(new Error('Google Maps failed to load'));
      document.head.appendChild(s);
    });
  }
  return loading;
}

/** Hide Google's POI pins/labels so our markers stay the focus. */
export const QUIET_MAP_STYLES = [
  { featureType: 'poi', stylers: [{ visibility: 'off' }] },
  { featureType: 'transit', stylers: [{ visibility: 'off' }] },
];
