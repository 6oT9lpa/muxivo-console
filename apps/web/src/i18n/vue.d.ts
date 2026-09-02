import type { TranslationParams } from "./index";

declare module "@vue/runtime-core" {
  interface ComponentCustomProperties {
    $t: (key: string, params?: TranslationParams) => string;
  }
}

export {};
