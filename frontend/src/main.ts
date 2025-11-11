import { createApp } from "vue";
import { createPinia } from "pinia";
import App from "./App.vue";
import "./styles/base.css";

const root = document.documentElement;
if (!root.classList.contains("theme-dark") && !root.classList.contains("theme-light")) {
  root.classList.add("theme-dark");
}

const app = createApp(App);
app.use(createPinia());
app.mount("#app");
