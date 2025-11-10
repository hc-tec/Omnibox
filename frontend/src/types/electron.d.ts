export type DesktopBridge = {
  getVersion: () => Promise<string>;
};

declare global {
  interface Window {
    desktop?: DesktopBridge;
  }
}

export {};
