import type { NextConfig } from "next";
import { resolveApiUrl } from "./src/lib/api-url.ts";

const apiUrl = resolveApiUrl(process.env.NEXT_PUBLIC_ATLAS_API_URL, process.env.NODE_ENV === "production");
const nextConfig: NextConfig = { env: { NEXT_PUBLIC_ATLAS_API_URL: apiUrl } };

export default nextConfig;
