export type DesktopBridge = {
  getVersion: () => Promise<string>;
  windowControls: {
    command: (action: "minimize" | "maximize" | "restore" | "close") => Promise<void>;
    isMaximized: () => Promise<boolean>;
    onStateChange: (callback: (isMaximized: boolean) => void) => () => void;
  };
};

declare global {
  interface Window {
    desktop?: DesktopBridge;
  }
}

export {};
