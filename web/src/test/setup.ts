import '@testing-library/jest-dom/vitest';

// API navigateur absentes de jsdom (Recharts et la navigation en ont besoin).
class ResizeObserverStub {
  observe() {}
  unobserve() {}
  disconnect() {}
}
globalThis.ResizeObserver ??= ResizeObserverStub as unknown as typeof ResizeObserver;
window.scrollTo = () => {};
