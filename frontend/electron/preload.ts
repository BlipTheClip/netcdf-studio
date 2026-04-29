import { contextBridge, ipcRenderer } from "electron";

contextBridge.exposeInMainWorld("electronAPI", {
  openFile: (): Promise<string | null> =>
    ipcRenderer.invoke("dialog:openFile"),

  saveFile: (defaultName: string): Promise<string | null> =>
    ipcRenderer.invoke("dialog:saveFile", defaultName),
});
