import { readonly, ref } from "vue";
import en from "./locales/en.json";
import ru from "./locales/ru.json";

export type Locale = "en" | "ru";
export type TranslationParams = Record<string, string | number>;

const STORAGE_KEY = "muxivo-discord.activity.locale";
const dictionaries: Record<Locale, Record<string, string>> = { en, ru };
const missingKeys = new Set<string>();

function browserLocale(): Locale {
  if (typeof window === "undefined") return "en";
  const stored = window.localStorage.getItem(STORAGE_KEY);
  if (stored === "en" || stored === "ru") return stored;
  return window.navigator.language.toLowerCase().startsWith("ru") ? "ru" : "en";
}

const activeLocale = ref<Locale>(browserLocale());

function interpolate(message: string, params: TranslationParams): string {
  return message.replace(/\{(\w+)\}/g, (placeholder, key: string) =>
    Object.prototype.hasOwnProperty.call(params, key) ? String(params[key]) : placeholder,
  );
}

export function t(key: string, params: TranslationParams = {}): string {
  const message = dictionaries[activeLocale.value][key] ?? dictionaries.en[key];
  if (!message) {
    if (!missingKeys.has(key)) {
      missingKeys.add(key);
      console.warn(`[i18n] Missing translation key: ${key}`);
    }
    return key;
  }
  return interpolate(message, params);
}

export function setLocale(locale: Locale): void {
  activeLocale.value = locale;
  if (typeof document !== "undefined") document.documentElement.lang = locale;
  if (typeof window !== "undefined") window.localStorage.setItem(STORAGE_KEY, locale);
  console.info(`[Muxivo Console] locale.changed`, { locale });
}

export function initializeLocale(): void {
  setLocale(activeLocale.value);
}

export function useI18n() {
  return {
    locale: readonly(activeLocale),
    setLocale,
    t,
  };
}
