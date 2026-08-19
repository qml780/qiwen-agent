import { Suspense } from "react";
import { Studio } from "@/components/studio";

export default function StudioPage() {
  return <Suspense fallback={<main className="loading-screen">正在准备创作室……</main>}><Studio /></Suspense>;
}
