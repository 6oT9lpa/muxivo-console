<script setup lang="ts">
type AuthProvider = "discord" | "twitch" | "telegram" | "google" | "yandex";

defineProps<{
  provider: AuthProvider;
}>();
</script>

<template>
  <svg
    class="auth-provider-icon"
    :class="`auth-provider-icon-${provider}`"
    viewBox="0 0 24 24"
    width="22"
    height="22"
    fill="none"
    aria-hidden="true"
    focusable="false"
  >
    <!-- Discord brand mark: the controller silhouette stays legible at compact sizes. -->
    <path
      v-if="provider === 'discord'"
      fill="currentColor"
      d="M19.54 5.06A16.6 16.6 0 0 0 15.42 3.8l-.5 1.03a15.3 15.3 0 0 0-5.84 0L8.58 3.8a16.6 16.6 0 0 0-4.12 1.26C1.85 8.84 1.14 12.53 1.5 16.17a16.65 16.65 0 0 0 5.06 2.54l1.22-1.64c-.67-.25-1.32-.57-1.93-.94l.47-.36c3.73 1.75 7.78 1.75 11.46 0l.47.36c-.61.37-1.26.69-1.93.94l1.22 1.64a16.65 16.65 0 0 0 5.06-2.54c.42-4.22-.72-7.88-3.06-11.11ZM8.57 14.08c-1.1 0-2-1.01-2-2.25s.88-2.25 2-2.25c1.13 0 2.02 1.01 2 2.25 0 1.24-.88 2.25-2 2.25Zm6.86 0c-1.1 0-2-1.01-2-2.25s.88-2.25 2-2.25c1.13 0 2.02 1.01 2 2.25 0 1.24-.88 2.25-2 2.25Z"
    />

    <!-- Twitch wordmark shape. -->
    <path
      v-else-if="provider === 'twitch'"
      fill="currentColor"
      d="M4 2h16v11.4l-4.1 4.1h-3.1l-2 2H8v-2H4V2Zm2 2v11.5h3v2l2-2h3l4-4V4H6Zm4 2h2v5h-2V6Zm4 0h2v5h-2V6Z"
    />

    <!-- Telegram paper plane. -->
    <path
      v-else-if="provider === 'telegram'"
      fill="currentColor"
      d="m21.6 3.4-3.03 16.18c-.23 1.14-.83 1.42-1.69.89l-4.67-3.44-2.25 2.17c-.25.25-.46.46-.94.46l.34-4.76 8.67-7.84c.38-.34-.08-.53-.59-.19L6.73 13.5l-4.58-1.43c-1-.31-1.02-1-.21-1.48L19.86 3.1c.85-.31 1.59.19 1.74.3Z"
    />

    <!-- Google G, using the provider colour as the accessible foreground. -->
    <path
      v-else-if="provider === 'google'"
      fill="currentColor"
      d="M21.35 12.27c0-.73-.07-1.43-.22-2.1H12v3.98h5.24a4.48 4.48 0 0 1-1.94 2.94v2.45h3.14c1.84-1.7 2.91-4.2 2.91-7.27ZM12 21.6c2.63 0 4.84-.87 6.45-2.36l-3.14-2.45c-.87.58-1.98.92-3.31.92-2.54 0-4.69-1.72-5.46-4.03H3.29v2.53A9.74 9.74 0 0 0 12 21.6ZM6.54 13.68a5.85 5.85 0 0 1 0-3.36V7.79H3.29a9.74 9.74 0 0 0 0 8.42l3.25-2.53ZM12 6.29c1.43 0 2.71.49 3.72 1.46l2.79-2.79C16.84 3.38 14.63 2.4 12 2.4a9.74 9.74 0 0 0-8.71 5.39l3.25 2.53C7.31 8.01 9.46 6.29 12 6.29Z"
    />

    <!-- Yandex ID uses its Cyrillic wordmark in a dedicated vector glyph. -->
    <text
      v-else
      x="12"
      y="18"
      text-anchor="middle"
      fill="currentColor"
      font-family="Arial, sans-serif"
      font-size="17"
      font-weight="800"
    >Я</text>
  </svg>
</template>
