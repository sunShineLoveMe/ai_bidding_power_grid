import { useEffect, useRef } from 'react';
import * as THREE from 'three';

interface GridKnowledgeSceneProps {
  variant: 'login' | 'register';
}

export function GridKnowledgeScene({ variant }: GridKnowledgeSceneProps): JSX.Element {
  const containerRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    const container = containerRef.current;
    if (!container) return undefined;

    const scene = new THREE.Scene();
    const camera = new THREE.PerspectiveCamera(48, 1, 0.1, 100);
    camera.position.set(0, 0.35, 9);

    const renderer = new THREE.WebGLRenderer({ alpha: true, antialias: true });
    renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
    container.appendChild(renderer.domElement);

    const palette = variant === 'register'
      ? { primary: 0x2f6bff, secondary: 0x4dd8c8, point: 0xffffff }
      : { primary: 0x2f6bff, secondary: 0x25d4ff, point: 0xffffff };

    const root = new THREE.Group();
    scene.add(root);

    const gridGroup = new THREE.Group();
    const gridMaterial = new THREE.LineBasicMaterial({
      color: palette.secondary,
      transparent: true,
      opacity: 0.16,
    });
    for (let index = -8; index <= 8; index += 1) {
      const horizontal = new THREE.BufferGeometry().setFromPoints([
        new THREE.Vector3(-7, index * 0.38, -2.4),
        new THREE.Vector3(7, index * 0.38, -2.4),
      ]);
      const vertical = new THREE.BufferGeometry().setFromPoints([
        new THREE.Vector3(index * 0.52, -3.2, -2.4),
        new THREE.Vector3(index * 0.52, 3.2, -2.4),
      ]);
      gridGroup.add(new THREE.Line(horizontal, gridMaterial));
      gridGroup.add(new THREE.Line(vertical, gridMaterial));
    }
    gridGroup.rotation.x = -0.92;
    gridGroup.position.set(-0.6, -2.25, 0);
    root.add(gridGroup);

    const particleCount = 180;
    const particlePositions = new Float32Array(particleCount * 3);
    for (let index = 0; index < particleCount; index += 1) {
      particlePositions[index * 3] = (Math.random() - 0.5) * 12;
      particlePositions[index * 3 + 1] = (Math.random() - 0.48) * 6;
      particlePositions[index * 3 + 2] = (Math.random() - 0.5) * 5;
    }
    const particleGeometry = new THREE.BufferGeometry();
    particleGeometry.setAttribute('position', new THREE.BufferAttribute(particlePositions, 3));
    const particleMaterial = new THREE.PointsMaterial({
      color: palette.point,
      size: 0.045,
      transparent: true,
      opacity: 0.68,
      blending: THREE.AdditiveBlending,
      depthWrite: false,
    });
    const particles = new THREE.Points(particleGeometry, particleMaterial);
    root.add(particles);

    const ringMaterial = new THREE.MeshBasicMaterial({
      color: palette.primary,
      transparent: true,
      opacity: 0.2,
      blending: THREE.AdditiveBlending,
      depthWrite: false,
    });
    const rings = new THREE.Group();
    [1.25, 1.95, 2.7].forEach((radius, index) => {
      const ring = new THREE.Mesh(new THREE.TorusGeometry(radius, 0.012, 8, 160), ringMaterial);
      ring.rotation.x = Math.PI * (0.42 + index * 0.06);
      ring.rotation.y = Math.PI * (0.1 + index * 0.08);
      rings.add(ring);
    });
    rings.position.set(2.6, 0.18, -0.4);
    root.add(rings);

    const core = new THREE.Mesh(
      new THREE.IcosahedronGeometry(0.42, 1),
      new THREE.MeshBasicMaterial({
        color: palette.primary,
        transparent: true,
        opacity: 0.72,
        blending: THREE.AdditiveBlending,
      }),
    );
    core.position.set(2.6, 0.18, -0.4);
    root.add(core);

    let frameId = 0;
    const resize = () => {
      const width = Math.max(container.clientWidth, 1);
      const height = Math.max(container.clientHeight, 1);
      renderer.setSize(width, height);
      camera.aspect = width / height;
      camera.updateProjectionMatrix();
    };
    resize();
    const observer = new ResizeObserver(resize);
    observer.observe(container);

    const prefersReducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    const animate = () => {
      const time = performance.now() * 0.001;
      particles.rotation.y = time * 0.035;
      particles.rotation.x = Math.sin(time * 0.24) * 0.035;
      gridGroup.position.y = -2.25 + Math.sin(time * 0.7) * 0.05;
      rings.rotation.z = time * 0.12;
      rings.rotation.y = Math.sin(time * 0.32) * 0.18;
      core.rotation.x = time * 0.62;
      core.rotation.y = time * 0.5;
      root.rotation.z = Math.sin(time * 0.18) * 0.025;
      renderer.render(scene, camera);
      if (!prefersReducedMotion) {
        frameId = requestAnimationFrame(animate);
      }
    };
    animate();

    return () => {
      cancelAnimationFrame(frameId);
      observer.disconnect();
      renderer.dispose();
      gridMaterial.dispose();
      particleMaterial.dispose();
      ringMaterial.dispose();
      scene.traverse(object => {
        if (object instanceof THREE.Mesh || object instanceof THREE.Line || object instanceof THREE.Points) {
          object.geometry.dispose();
        }
      });
      renderer.domElement.remove();
    };
  }, [variant]);

  return <div ref={containerRef} className="auth-grid-scene" aria-hidden="true" />;
}
