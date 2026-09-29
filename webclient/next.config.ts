import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  output: "standalone",
  // Dev server only: allow the app to be opened through an ngrok tunnel. Without this the dev
  // server blocks the page's client resources, the form never hydrates and a sign-in submit
  // falls back to a plain GET that puts the password in the URL.
  allowedDevOrigins: ["*.ngrok-free.dev", "*.ngrok-free.app", "*.ngrok.app"],
  async headers() {
    // The invitation token is in this page's URL; never send it on as a Referer.
    return [
      {
        source: "/accept-invite",
        headers: [{ key: "Referrer-Policy", value: "no-referrer" }],
      },
    ];
  },
};

export default nextConfig;
