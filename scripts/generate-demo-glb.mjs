import { Accessor, Document, NodeIO } from "@gltf-transform/core";

const document = new Document();
const buffer = document.createBuffer("QIWEN Demo Buffer");

const positions = [];
const normals = [];
const indices = [];
const segments = 48;
const rings = 10;

for (let ring = 0; ring <= rings; ring += 1) {
  const t = ring / rings;
  const y = -0.7 + t * 1.15;
  const radius = 0.58 + Math.sin(t * Math.PI * 0.72) * 0.62;
  for (let segment = 0; segment <= segments; segment += 1) {
    const angle = (segment / segments) * Math.PI * 2;
    positions.push(Math.cos(angle) * radius, y, Math.sin(angle) * radius);
    const nx = Math.cos(angle);
    const nz = Math.sin(angle);
    normals.push(nx * 0.72, 0.22, nz * 0.72);
  }
}

for (let ring = 0; ring < rings; ring += 1) {
  for (let segment = 0; segment < segments; segment += 1) {
    const row = segments + 1;
    const a = ring * row + segment;
    const b = a + row;
    indices.push(a, b, a + 1, b, b + 1, a + 1);
  }
}

const positionAccessor = document
  .createAccessor("POSITION")
  .setType(Accessor.Type.VEC3)
  .setArray(new Float32Array(positions))
  .setBuffer(buffer);
const normalAccessor = document
  .createAccessor("NORMAL")
  .setType(Accessor.Type.VEC3)
  .setArray(new Float32Array(normals))
  .setBuffer(buffer);
const indexAccessor = document
  .createAccessor("INDICES")
  .setType(Accessor.Type.SCALAR)
  .setArray(new Uint16Array(indices))
  .setBuffer(buffer);

const material = document
  .createMaterial("Black Lacquer")
  .setBaseColorFactor([0.055, 0.045, 0.04, 1])
  .setMetallicFactor(0.18)
  .setRoughnessFactor(0.16);

const primitive = document
  .createPrimitive()
  .setAttribute("POSITION", positionAccessor)
  .setAttribute("NORMAL", normalAccessor)
  .setIndices(indexAccessor)
  .setMaterial(material);

const mesh = document.createMesh("Lacquer Bowl").addPrimitive(primitive);
const node = document.createNode("Lacquer Bowl v1").setMesh(mesh);
const scene = document.createScene("QIWEN Demo 3D").addChild(node);
document.getRoot().setDefaultScene(scene);

const io = new NodeIO();
await io.write("apps/web/public/demo/lacquer-bowl-v1.glb", document);

