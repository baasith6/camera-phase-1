import { Injectable, signal, Signal } from '@angular/core';

/** Wraps a matchMedia query into a reactive signal. */
function mediaSignal(query: string): Signal<boolean> {
  if (typeof window === 'undefined' || !window.matchMedia) {
    return signal(true).asReadonly();
  }
  const mql = window.matchMedia(query);
  const state = signal(mql.matches);
  mql.addEventListener('change', (e) => state.set(e.matches));
  return state.asReadonly();
}

/**
 * Viewport breakpoint signals aligned with the Tailwind defaults.
 * Use ONLY where behavior (navigation, data loading) genuinely differs by
 * viewport — pure layout should use responsive utility classes instead.
 */
@Injectable({ providedIn: 'root' })
export class BreakpointService {
  /** ≥1024px — `lg`: master-detail split, persistent sidebar. */
  readonly isLgUp = mediaSignal('(min-width: 1024px)');
  /** ≥768px — `md`: tables instead of mobile cards. */
  readonly isMdUp = mediaSignal('(min-width: 768px)');
}
