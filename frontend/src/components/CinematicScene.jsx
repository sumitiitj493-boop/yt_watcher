import { useEffect, useRef } from 'react';
import * as THREE from 'three';
import './CinematicScene.css';

const clamp = (value, min, max) => Math.max(min, Math.min(max, value));
const lerp = (a, b, t) => a + (b - a) * t;

function makeParticle(width, height, random = Math.random) {
  const z = random();
  return {
    x: random() * width,
    y: random() * height,
    z,
    r: lerp(0.35, 2.7, z),
    vx: lerp(-0.08, 0.08, random()) * lerp(0.35, 1.8, z),
    vy: lerp(0.08, 0.42, random()) * lerp(0.45, 1.55, z),
    hue: lerp(188, 278, random()),
    alpha: lerp(0.12, 0.72, z),
    pulse: random() * Math.PI * 2,
  };
}

function drawGlow(ctx, x, y, radius, colorStops) {
  const gradient = ctx.createRadialGradient(x, y, 0, x, y, radius);
  colorStops.forEach(([stop, color]) => gradient.addColorStop(stop, color));
  ctx.fillStyle = gradient;
  ctx.beginPath();
  ctx.arc(x, y, radius, 0, Math.PI * 2);
  ctx.fill();
}

function createSoftTexture() {
  const canvas = document.createElement('canvas');
  canvas.width = 128;
  canvas.height = 128;
  const ctx = canvas.getContext('2d');
  const g = ctx.createRadialGradient(64, 64, 0, 64, 64, 64);
  g.addColorStop(0, 'rgba(255,255,255,1)');
  g.addColorStop(0.18, 'rgba(180,235,255,0.55)');
  g.addColorStop(0.48, 'rgba(139,92,246,0.20)');
  g.addColorStop(1, 'rgba(255,255,255,0)');
  ctx.fillStyle = g;
  ctx.fillRect(0, 0, 128, 128);
  const texture = new THREE.CanvasTexture(canvas);
  texture.colorSpace = THREE.SRGBColorSpace;
  return texture;
}

export default function CinematicScene() {
  const enableWebGL = import.meta.env.VITE_ENABLE_WEBGL_SCENE === 'true';
  const threeRef = useRef(null);
  const canvasRef = useRef(null);
  const mouseRef = useRef({ x: 0.5, y: 0.35, tx: 0.5, ty: 0.35, active: false });

  // True WebGL/Three.js dimensional scene: floating nebula, 3D rings, crystal, depth particles.
  useEffect(() => {
    if (!enableWebGL) return undefined;
    const canvas = threeRef.current;
    if (!canvas) return undefined;

    const reducedMotion = window.matchMedia?.('(prefers-reduced-motion: reduce)').matches;
    let renderer;
    try {
      renderer = new THREE.WebGLRenderer({ canvas, alpha: true, antialias: true, powerPreference: 'high-performance' });
    } catch {
      return undefined;
    }

    const scene = new THREE.Scene();
    scene.fog = new THREE.FogExp2(0x050713, 0.045);

    const camera = new THREE.PerspectiveCamera(58, window.innerWidth / window.innerHeight, 0.1, 120);
    camera.position.set(0, 0.8, 13.5);

    const root = new THREE.Group();
    scene.add(root);

    const texture = createSoftTexture();
    const nebulaMaterial = new THREE.SpriteMaterial({
      map: texture,
      transparent: true,
      opacity: 0.22,
      blending: THREE.AdditiveBlending,
      depthWrite: false,
      color: new THREE.Color('#7c3aed'),
    });

    const nebulaSprites = [];
    for (let i = 0; i < 18; i += 1) {
      const sprite = new THREE.Sprite(nebulaMaterial.clone());
      sprite.position.set((Math.random() - 0.5) * 24, (Math.random() - 0.5) * 12, -8 - Math.random() * 36);
      const scale = 5 + Math.random() * 12;
      sprite.scale.set(scale, scale, 1);
      sprite.material.color = new THREE.Color().setHSL(0.52 + Math.random() * 0.28, 0.95, 0.62);
      sprite.material.opacity = 0.08 + Math.random() * 0.18;
      nebulaSprites.push(sprite);
      root.add(sprite);
    }

    const particleCount = reducedMotion ? 700 : 1800;
    const positions = new Float32Array(particleCount * 3);
    const colors = new Float32Array(particleCount * 3);
    const sizes = new Float32Array(particleCount);
    const color = new THREE.Color();
    for (let i = 0; i < particleCount; i += 1) {
      const i3 = i * 3;
      positions[i3] = (Math.random() - 0.5) * 34;
      positions[i3 + 1] = (Math.random() - 0.5) * 18;
      positions[i3 + 2] = -Math.random() * 70;
      color.setHSL(0.52 + Math.random() * 0.28, 0.92, 0.62 + Math.random() * 0.28);
      colors[i3] = color.r;
      colors[i3 + 1] = color.g;
      colors[i3 + 2] = color.b;
      sizes[i] = 0.03 + Math.random() * 0.16;
    }
    const particleGeometry = new THREE.BufferGeometry();
    particleGeometry.setAttribute('position', new THREE.BufferAttribute(positions, 3));
    particleGeometry.setAttribute('color', new THREE.BufferAttribute(colors, 3));
    const particleMaterial = new THREE.PointsMaterial({
      size: 0.065,
      vertexColors: true,
      transparent: true,
      opacity: 0.82,
      blending: THREE.AdditiveBlending,
      depthWrite: false,
      map: texture,
    });
    const starfield = new THREE.Points(particleGeometry, particleMaterial);
    root.add(starfield);

    const ringGroup = new THREE.Group();
    ringGroup.position.set(3.6, -0.7, -8.2);
    root.add(ringGroup);
    for (let i = 0; i < 5; i += 1) {
      const geometry = new THREE.TorusGeometry(2.2 + i * 0.34, 0.008 + i * 0.003, 10, 180);
      const material = new THREE.MeshBasicMaterial({
        color: new THREE.Color().setHSL(0.55 + i * 0.035, 0.95, 0.66),
        transparent: true,
        opacity: 0.18 - i * 0.018,
        blending: THREE.AdditiveBlending,
        depthWrite: false,
      });
      const torus = new THREE.Mesh(geometry, material);
      torus.rotation.set(Math.PI / 2.7 + i * 0.12, i * 0.36, i * 0.42);
      ringGroup.add(torus);
    }

    const crystalGeometry = new THREE.IcosahedronGeometry(1.05, 2);
    const crystalMaterial = new THREE.MeshPhysicalMaterial({
      color: 0x93c5fd,
      roughness: 0.12,
      metalness: 0.08,
      transmission: 0.58,
      thickness: 0.8,
      transparent: true,
      opacity: 0.36,
      emissive: 0x1d4ed8,
      emissiveIntensity: 0.12,
      clearcoat: 1,
      clearcoatRoughness: 0.05,
    });
    const crystal = new THREE.Mesh(crystalGeometry, crystalMaterial);
    crystal.position.set(-4.1, 1.2, -7.6);
    root.add(crystal);

    const wire = new THREE.Mesh(
      new THREE.IcosahedronGeometry(1.09, 1),
      new THREE.MeshBasicMaterial({ color: 0x67e8f9, transparent: true, opacity: 0.18, wireframe: true, blending: THREE.AdditiveBlending }),
    );
    crystal.add(wire);

    const keyLight = new THREE.PointLight(0x8b5cf6, 32, 28);
    keyLight.position.set(-5, 5, 6);
    scene.add(keyLight);
    const cyanLight = new THREE.PointLight(0x22d3ee, 24, 26);
    cyanLight.position.set(6, -2, 5);
    scene.add(cyanLight);
    scene.add(new THREE.AmbientLight(0x7dd3fc, 0.32));

    let width = 1;
    let height = 1;
    let animationId = 0;
    const clock = new THREE.Clock();

    const resize = () => {
      width = window.innerWidth;
      height = window.innerHeight;
      renderer.setPixelRatio(clamp(window.devicePixelRatio || 1, 1, 1.6));
      renderer.setSize(width, height, false);
      camera.aspect = width / Math.max(1, height);
      camera.updateProjectionMatrix();
    };

    const animate = () => {
      const elapsed = clock.getElapsedTime();
      const mouse = mouseRef.current;
      const px = (mouse.x - 0.5) * 2;
      const py = (mouse.y - 0.5) * 2;

      camera.position.x = lerp(camera.position.x, px * 0.9, 0.035);
      camera.position.y = lerp(camera.position.y, 0.8 - py * 0.55, 0.035);
      camera.lookAt(px * 0.5, -py * 0.2, -8);

      root.rotation.y = elapsed * 0.025 + px * 0.045;
      root.rotation.x = -py * 0.025;
      starfield.rotation.y = elapsed * 0.012;
      starfield.rotation.x = elapsed * 0.003;

      ringGroup.rotation.x = elapsed * 0.18;
      ringGroup.rotation.y = elapsed * 0.13 + px * 0.28;
      ringGroup.rotation.z = elapsed * 0.08;
      crystal.rotation.x = elapsed * 0.28 + py * 0.18;
      crystal.rotation.y = elapsed * 0.36 + px * 0.22;
      crystal.position.y = 1.2 + Math.sin(elapsed * 1.1) * 0.22;

      for (let i = 0; i < nebulaSprites.length; i += 1) {
        const sprite = nebulaSprites[i];
        sprite.position.x += Math.sin(elapsed * 0.18 + i) * 0.0015;
        sprite.position.y += Math.cos(elapsed * 0.16 + i * 1.7) * 0.0015;
        sprite.material.opacity = 0.08 + Math.sin(elapsed * 0.5 + i) * 0.025 + (i % 3) * 0.018;
      }

      renderer.render(scene, camera);
      if (!reducedMotion) animationId = requestAnimationFrame(animate);
    };

    resize();
    window.addEventListener('resize', resize);
    animationId = requestAnimationFrame(animate);

    return () => {
      cancelAnimationFrame(animationId);
      window.removeEventListener('resize', resize);
      particleGeometry.dispose();
      particleMaterial.dispose();
      crystalGeometry.dispose();
      crystalMaterial.dispose();
      texture.dispose();
      renderer.dispose();
    };
  }, [enableWebGL]);

  // 2D cinematic overlay: aurora, lens flare, meteors, grain-friendly particles.
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return undefined;

    const ctx = canvas.getContext('2d', { alpha: true });
    if (!ctx) return undefined;

    let width = 1;
    let height = 1;
    let dpr = 1;
    let frame = 0;
    let animationId = 0;
    let particles = [];
    let meteors = [];
    let lastTime = performance.now();
    let meteorTimer = 0;
    const reducedMotion = window.matchMedia?.('(prefers-reduced-motion: reduce)').matches;

    const resize = () => {
      dpr = clamp(window.devicePixelRatio || 1, 1, 1.75);
      width = window.innerWidth;
      height = window.innerHeight;
      canvas.width = Math.floor(width * dpr);
      canvas.height = Math.floor(height * dpr);
      canvas.style.width = `${width}px`;
      canvas.style.height = `${height}px`;
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      const count = reducedMotion ? 45 : clamp(Math.floor((width * height) / 14000), 70, 170);
      particles = Array.from({ length: count }, () => makeParticle(width, height));
    };

    const onPointerMove = (event) => {
      mouseRef.current.tx = event.clientX / Math.max(1, width);
      mouseRef.current.ty = event.clientY / Math.max(1, height);
      mouseRef.current.active = true;
    };

    const onPointerLeave = () => {
      mouseRef.current.tx = 0.5;
      mouseRef.current.ty = 0.35;
      mouseRef.current.active = false;
    };

    const spawnMeteor = () => {
      meteors.push({
        x: Math.random() * width * 0.9,
        y: -40,
        vx: lerp(4, 9, Math.random()),
        vy: lerp(7, 13, Math.random()),
        life: 0,
        maxLife: lerp(45, 90, Math.random()),
        hue: lerp(190, 260, Math.random()),
      });
      if (meteors.length > 4) meteors.shift();
    };

    const drawAuroraRibbon = (time, index, hue, alpha, offsetY, amplitude, thickness) => {
      ctx.save();
      ctx.globalCompositeOperation = 'lighter';
      ctx.lineWidth = thickness;
      ctx.lineCap = 'round';
      const gradient = ctx.createLinearGradient(0, offsetY - amplitude, width, offsetY + amplitude);
      gradient.addColorStop(0, `hsla(${hue - 45}, 90%, 62%, 0)`);
      gradient.addColorStop(0.22, `hsla(${hue}, 95%, 67%, ${alpha})`);
      gradient.addColorStop(0.52, `hsla(${hue + 42}, 96%, 64%, ${alpha * 0.82})`);
      gradient.addColorStop(0.84, `hsla(${hue + 86}, 92%, 62%, ${alpha * 0.55})`);
      gradient.addColorStop(1, `hsla(${hue + 120}, 88%, 62%, 0)`);
      ctx.strokeStyle = gradient;
      ctx.beginPath();
      for (let x = -80; x <= width + 80; x += 22) {
        const nx = x / width;
        const y = offsetY
          + Math.sin(nx * 7.2 + time * (0.45 + index * 0.08) + index) * amplitude
          + Math.sin(nx * 17 + time * 0.22 + index * 1.7) * amplitude * 0.32;
        if (x === -80) ctx.moveTo(x, y);
        else ctx.lineTo(x, y);
      }
      ctx.stroke();
      ctx.restore();
    };

    const render = (now) => {
      const dt = clamp((now - lastTime) / 16.666, 0.35, 2.2);
      lastTime = now;
      frame += dt;
      const time = frame / 60;
      const mouse = mouseRef.current;
      mouse.x = lerp(mouse.x, mouse.tx, 0.045);
      mouse.y = lerp(mouse.y, mouse.ty, 0.045);
      const parallaxX = (mouse.x - 0.5) * 2;
      const parallaxY = (mouse.y - 0.5) * 2;

      ctx.clearRect(0, 0, width, height);

      drawGlow(ctx, width * (0.16 + parallaxX * 0.018), height * (0.12 + parallaxY * 0.012), Math.max(width, height) * 0.5, [
        [0, 'rgba(139, 92, 246, 0.22)'], [0.33, 'rgba(80, 70, 229, 0.10)'], [1, 'rgba(80, 70, 229, 0)'],
      ]);
      drawGlow(ctx, width * (0.86 + parallaxX * -0.02), height * (0.2 + parallaxY * 0.02), Math.max(width, height) * 0.42, [
        [0, 'rgba(34, 211, 238, 0.18)'], [0.34, 'rgba(14, 165, 233, 0.08)'], [1, 'rgba(14, 165, 233, 0)'],
      ]);

      drawAuroraRibbon(time, 0, 215, 0.16, height * 0.23 + parallaxY * 20, 38, 28);
      drawAuroraRibbon(time, 1, 268, 0.14, height * 0.34 + parallaxY * 26, 56, 34);
      drawAuroraRibbon(time, 2, 186, 0.10, height * 0.49 + parallaxY * 18, 44, 24);

      ctx.save();
      ctx.globalCompositeOperation = 'lighter';
      for (const particle of particles) {
        particle.x += (particle.vx + parallaxX * 0.035 * particle.z) * dt;
        particle.y += (particle.vy + parallaxY * 0.018 * particle.z) * dt;
        particle.pulse += 0.025 * dt;
        if (particle.y > height + 20 || particle.x < -30 || particle.x > width + 30) {
          Object.assign(particle, makeParticle(width, height));
          particle.y = -12;
        }
        const twinkle = 0.65 + Math.sin(particle.pulse) * 0.35;
        const x = particle.x + parallaxX * particle.z * 36;
        const y = particle.y + parallaxY * particle.z * 22;
        ctx.fillStyle = `hsla(${particle.hue}, 95%, 78%, ${particle.alpha * twinkle})`;
        ctx.beginPath();
        ctx.arc(x, y, particle.r * lerp(0.5, 1.85, particle.z) * twinkle, 0, Math.PI * 2);
        ctx.fill();
      }
      ctx.restore();

      if (!reducedMotion) {
        meteorTimer += dt;
        if (meteorTimer > 120 + Math.random() * 90) { spawnMeteor(); meteorTimer = 0; }
      }
      ctx.save();
      ctx.globalCompositeOperation = 'lighter';
      meteors = meteors.filter((meteor) => meteor.life < meteor.maxLife && meteor.x < width + 200 && meteor.y < height + 200);
      for (const meteor of meteors) {
        meteor.life += dt;
        meteor.x += meteor.vx * dt;
        meteor.y += meteor.vy * dt;
        const alpha = 1 - meteor.life / meteor.maxLife;
        const gradient = ctx.createLinearGradient(meteor.x, meteor.y, meteor.x - 120, meteor.y - 90);
        gradient.addColorStop(0, `hsla(${meteor.hue}, 100%, 82%, ${0.72 * alpha})`);
        gradient.addColorStop(1, `hsla(${meteor.hue + 90}, 100%, 72%, 0)`);
        ctx.strokeStyle = gradient;
        ctx.lineWidth = 2.4;
        ctx.beginPath();
        ctx.moveTo(meteor.x, meteor.y);
        ctx.lineTo(meteor.x - 120, meteor.y - 90);
        ctx.stroke();
      }
      ctx.restore();

      drawGlow(ctx, width * mouse.x, height * mouse.y, 160, [
        [0, mouse.active ? 'rgba(255,255,255,0.10)' : 'rgba(255,255,255,0.045)'],
        [0.14, 'rgba(34,211,238,0.08)'],
        [0.5, 'rgba(139,92,246,0.035)'],
        [1, 'rgba(139,92,246,0)'],
      ]);

      const vignette = ctx.createRadialGradient(width * 0.5, height * 0.4, Math.min(width, height) * 0.1, width * 0.5, height * 0.5, Math.max(width, height) * 0.72);
      vignette.addColorStop(0, 'rgba(0,0,0,0)');
      vignette.addColorStop(0.72, 'rgba(0,0,0,0.10)');
      vignette.addColorStop(1, 'rgba(0,0,0,0.46)');
      ctx.fillStyle = vignette;
      ctx.fillRect(0, 0, width, height);

      if (!reducedMotion) animationId = requestAnimationFrame(render);
    };

    resize();
    window.addEventListener('resize', resize);
    window.addEventListener('pointermove', onPointerMove, { passive: true });
    window.addEventListener('pointerleave', onPointerLeave);
    animationId = requestAnimationFrame(render);

    return () => {
      cancelAnimationFrame(animationId);
      window.removeEventListener('resize', resize);
      window.removeEventListener('pointermove', onPointerMove);
      window.removeEventListener('pointerleave', onPointerLeave);
    };
  }, []);

  return (
    <div className="cinematic-scene" aria-hidden="true">
      {enableWebGL ? <canvas ref={threeRef} className="cinematic-scene__webgl" /> : null}
      <canvas ref={canvasRef} className="cinematic-scene__canvas" />
      <div className="cinematic-scene__depth cinematic-scene__depth--one" />
      <div className="cinematic-scene__depth cinematic-scene__depth--two" />
      <div className="cinematic-scene__grain" />
    </div>
  );
}
