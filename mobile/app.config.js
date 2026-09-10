const appJson = require("./app.json");

const DEFAULT_API_BASE_URL = "http://127.0.0.1:8000";

/** @type {import("expo/config").ExpoConfig} */
module.exports = {
  ...appJson,
  expo: {
    ...appJson.expo,
    name: "WhatsNews",
    splash: {
      ...appJson.expo.splash,
      backgroundColor: "#F5F6F8",
    },
    extra: {
      ...appJson.expo.extra,
      apiBaseUrl: process.env.EXPO_PUBLIC_API_BASE_URL ?? DEFAULT_API_BASE_URL,
    },
  },
};
