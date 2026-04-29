// Type declarations for the API exposed by electron/preload.ts via contextBridge.

interface ElectronAPI {
  openFile: () => Promise<string | null>;
  saveFile: (defaultName: string) => Promise<string | null>;
}

declare global {
  interface Window {
    electronAPI?: ElectronAPI;
  }
}

export {};
