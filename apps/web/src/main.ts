import { createApp } from "vue";
import App from "./App.vue";
import { initializeLocale, t } from "./i18n";
import "./styles.css";

initializeLocale();

const app = createApp(App);
app.config.globalProperties.$t = t;
app.mount("#app");
