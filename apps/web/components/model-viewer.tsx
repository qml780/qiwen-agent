"use client";

import { ContactShadows, Environment, OrbitControls, useGLTF } from "@react-three/drei";
import { Canvas } from "@react-three/fiber";
import { Suspense } from "react";

function Model({ url }: { url: string }) {
  const { scene } = useGLTF(url);
  return <primitive object={scene} rotation={[0, 0, 0]} />;
}

export function ModelViewer({ url }: { url: string }) {
  return (
    <div className="model-viewer" aria-label="可交互的三维模型查看器">
      <Canvas camera={{ position: [2.8, 1.8, 3.3], fov: 38 }} dpr={[1, 1.5]}>
        <color attach="background" args={["#f0f0f0"]} />
        <ambientLight intensity={1.2} />
        <directionalLight position={[4, 5, 3]} intensity={3.4} />
        <Suspense fallback={null}>
          <group position={[0, 0.25, 0]} scale={0.9}><Model url={url} /></group>
          <Environment preset="studio" />
          <ContactShadows position={[0, -0.75, 0]} opacity={0.26} scale={5} blur={2.5} />
        </Suspense>
        <OrbitControls makeDefault enablePan={false} minDistance={2.4} maxDistance={6} />
      </Canvas>
      <div className="viewer-hint">拖动旋转 · 滚轮缩放</div>
    </div>
  );
}

useGLTF.preload("/demo/lacquer-bowl-v1.glb");
