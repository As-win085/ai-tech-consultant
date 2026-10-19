/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_KNOWLEDGE_API_URL?: string;
  readonly VITE_INBOX_API_URL?: string;
  readonly VITE_MEETING_API_URL?: string;
  readonly VITE_DEMO_MODE?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}

declare module "*.svg" {
  const src: string;
  export default src;
}

declare module "*.png" {
  const src: string;
  export default src;
}
