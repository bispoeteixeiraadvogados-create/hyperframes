/*
 * BTField: lavoura em perspectiva desenhada em canvas 2D (soja trifoliada em fileiras,
 * sulcos, linhas de irrigacao com aspersores e particulas de velocidade).
 *
 * Funcao pura do estado recebido: o mesmo estado sempre produz os mesmos pixels, entao o
 * render com seek por quadro e deterministico. Usada pela abertura (rush) e, calma, pela
 * tela de marca.
 */
(function () {
  const W = 1080;
  const H = 1920;
  const FOCAL = 900;
  const ROW = 0.92;
  const STEP = 0.44;
  const Z_NEAR = 0.3;
  const Z_FAR = 44;
  const LEAF = ["#2b4529", "#31502e", "#385b32", "#3f6337", "#475b34", "#2f4e38"];
  const RIM = "rgba(176,202,146,";

  function hash(n) {
    let x = Math.imul(n | 0, 0x27d4eb2d) ^ 0x165667b1;
    x = Math.imul(x ^ (x >>> 15), 0x85ebca6b);
    x = Math.imul(x ^ (x >>> 13), 0xc2b2ae35);
    x ^= x >>> 16;
    return (x >>> 0) / 4294967295;
  }
  function smooth(e0, e1, x) {
    const u = Math.max(0, Math.min(1, (x - e0) / (e1 - e0)));
    return u * u * (3 - 2 * u);
  }

  // folha lanceolada com ponta: base em (0,0), ponta em (0,-len)
  function leafPath(ctx, x, y, ang, len, wid) {
    const c = Math.cos(ang);
    const s = Math.sin(ang);
    const P = (lx, ly) => [x + lx * c - ly * s, y + lx * s + ly * c];
    const tip = P(0, -len);
    const l1 = P(-wid, -len * 0.42);
    const r1 = P(wid, -len * 0.42);
    ctx.moveTo(x, y);
    ctx.quadraticCurveTo(l1[0], l1[1], tip[0], tip[1]);
    ctx.quadraticCurveTo(r1[0], r1[1], x, y);
    return tip;
  }

  function draw(ctx, o) {
    const pos = o.pos;
    const vel = o.vel || 0;
    const hy = o.hy;
    const camH = o.camH;
    const camX = o.camX || 0;
    const fade = o.fade === undefined ? 1 : o.fade;
    const press = o.press || 0;
    const gc = o.glow || [212, 167, 124];
    const glowA = o.glowA === undefined ? 0.3 : o.glowA;
    ctx.clearRect(0, 0, W, H);
    if (fade <= 0.001) return;
    ctx.globalAlpha = fade;

    // solo
    const soil = ctx.createLinearGradient(0, hy, 0, H);
    soil.addColorStop(0, "rgba(11,31,75,1)");
    soil.addColorStop(0.14, "rgba(9,23,46,1)");
    soil.addColorStop(1, "rgba(5,12,24,1)");
    ctx.fillStyle = soil;
    ctx.fillRect(0, hy, W, H - hy);

    // brilho do horizonte
    const hg = ctx.createLinearGradient(0, hy - 150, 0, hy + 170);
    hg.addColorStop(0, `rgba(${gc[0]},${gc[1]},${gc[2]},0)`);
    hg.addColorStop(0.47, `rgba(${gc[0]},${gc[1]},${gc[2]},${glowA})`);
    hg.addColorStop(0.53, `rgba(${gc[0]},${gc[1]},${gc[2]},${glowA * 0.85})`);
    hg.addColorStop(1, `rgba(${gc[0]},${gc[1]},${gc[2]},0)`);
    ctx.fillStyle = hg;
    ctx.fillRect(0, hy - 150, W, 320);

    // sulcos convergindo
    ctx.lineCap = "round";
    const halfFar = W / 2 / (FOCAL / Z_FAR);
    const iMin = Math.floor((camX - halfFar - 2) / ROW);
    const iMax = Math.ceil((camX + halfFar + 2) / ROW);
    for (let i = iMin; i <= iMax; i++) {
      const x = i * ROW - camX + ROW * 0.5;
      const x0 = W / 2 + (x * FOCAL) / Z_FAR;
      const y0 = hy + (camH * FOCAL) / Z_FAR;
      const x1 = W / 2 + (x * FOCAL) / Z_NEAR;
      const y1 = hy + (camH * FOCAL) / Z_NEAR;
      const g = ctx.createLinearGradient(x0, y0, x1, y1);
      g.addColorStop(0, "rgba(40,60,52,0)");
      g.addColorStop(0.2, "rgba(48,70,58,0.35)");
      g.addColorStop(1, "rgba(58,82,64,0.5)");
      ctx.strokeStyle = g;
      ctx.lineWidth = 1.6;
      ctx.beginPath();
      ctx.moveTo(x0, y0);
      ctx.lineTo(x1, y1);
      ctx.stroke();
    }

    // linhas de irrigacao (fixas no mundo)
    if (o.irrigation !== false) {
      const IRR = 7.5;
      const kFar = Math.floor((pos + Z_FAR) / IRR);
      const kNear = Math.ceil((pos + Z_NEAR) / IRR);
      for (let k = kFar; k >= kNear; k--) {
        const z = k * IRR - pos;
        if (z < Z_NEAR || z > Z_FAR) continue;
        const s = FOCAL / z;
        const y = hy + camH * s;
        const a = (1 - smooth(5, Z_FAR, z)) * smooth(0.9, 2.4, z) * 0.32;
        ctx.strokeStyle = `rgba(150,176,122,${a})`;
        ctx.lineWidth = Math.max(1, 0.018 * s);
        ctx.beginPath();
        ctx.moveTo(0, y);
        ctx.lineTo(W, y);
        ctx.stroke();
        const half = W / 2 / s;
        const i0 = Math.floor((camX - half) / (ROW * 3));
        const i1 = Math.ceil((camX + half) / (ROW * 3));
        for (let i = i0; i <= i1; i++) {
          const sx = W / 2 + (i * ROW * 3 - camX) * s;
          const r = Math.min(4, Math.max(1, 0.022 * s));
          ctx.fillStyle = `rgba(250,248,244,${a * 1.5})`;
          ctx.beginPath();
          ctx.arc(sx, y - r, r, 0, Math.PI * 2);
          ctx.fill();
        }
      }
    }

    // plantas, do fundo para a frente
    const shutter = 1 / 50;
    const jFar = Math.floor((pos + Z_FAR) / STEP);
    const jNear = Math.ceil((pos + Z_NEAR) / STEP);
    for (let j = jFar; j >= jNear; j--) {
      const z = j * STEP - pos;
      if (z < Z_NEAR || z > Z_FAR) continue;
      const s = FOCAL / z;
      const half = W / 2 / s;
      const fog = smooth(4, Z_FAR, z);
      const i0 = Math.floor((camX - half - 1) / ROW);
      const i1 = Math.ceil((camX + half + 1) / ROW);
      for (let i = i0; i <= i1; i++) {
        const r1 = hash(i * 7919 + j * 104729);
        const r2 = hash(i * 31 + j * 1777 + 5);
        const r3 = hash(i * 977 + j * 61 + 11);
        const x = i * ROW + (r1 - 0.5) * 0.1 - camX;
        const hgt = 0.22 + 0.2 * r2;
        const sx = W / 2 + x * s;
        const sy = hy + (camH - hgt) * s;
        const size = (0.2 + 0.08 * r3) * s;
        if (
          size < 0.8 ||
          sx < -size * 2 ||
          sx > W + size * 2 ||
          sy > H + size * 2 ||
          sy < -size * 2
        )
          continue;
        const col = LEAF[(r1 * LEAF.length) | 0];
        const alpha = (1 - fog * 0.92) * (1 - 0.3 * press);
        // rastro de movimento: deslocamento de tela durante o obturador
        const dz = vel * shutter;
        const s2 = FOCAL / (z + dz);
        const px = W / 2 + x * s2;
        const py = hy + (camH - hgt) * s2;
        const trail = Math.hypot(sx - px, sy - py);
        const rot = (r2 - 0.5) * 0.7;
        if (trail > size * 0.35) {
          // borrao de movimento: copias-fantasma do proprio trifolio ao longo do trajeto
          const N = 7;
          ctx.fillStyle = col;
          for (let g = 0; g < N; g++) {
            const u = g / (N - 1);
            const gx = px + (sx - px) * u;
            const gy = py + (sy - py) * u;
            const gs = size * (0.55 + 0.45 * u);
            ctx.globalAlpha = fade * alpha * (0.07 + 0.16 * u);
            ctx.beginPath();
            for (let L = -1; L <= 1; L++) {
              const ang = rot + L * (0.95 + 0.2 * r3);
              leafPath(ctx, gx, gy, ang, gs * (L === 0 ? 0.95 : 0.78), gs * 0.3);
            }
            ctx.fill();
          }
          continue;
        }
        ctx.globalAlpha = fade * alpha;
        ctx.fillStyle = col;
        ctx.beginPath();
        const tips = [];
        for (let L = -1; L <= 1; L++) {
          const ang = rot + L * (0.95 + 0.2 * r3);
          const len = size * (L === 0 ? 0.95 : 0.78);
          tips.push([ang, len]);
          leafPath(ctx, sx, sy, ang, len, size * 0.3);
        }
        ctx.fill();
        if (size > 5) {
          // nervura central e luz de borda (oliva claro, discreta)
          ctx.globalAlpha = fade * alpha * 0.7;
          ctx.strokeStyle = RIM + (0.32 + 0.25 * (1 - press)) + ")";
          ctx.lineWidth = Math.max(0.8, size * 0.035);
          ctx.beginPath();
          for (const [ang, len] of tips) {
            ctx.moveTo(sx, sy);
            ctx.lineTo(sx + Math.sin(ang) * len * 0.85, sy - Math.cos(ang) * len * 0.85);
          }
          ctx.stroke();
        }
      }
    }

    // particulas de velocidade (polen e poeira riscando em direcao a camera)
    if (o.particles && vel > 3) {
      const N = 90;
      const span = 26;
      ctx.lineCap = "round";
      for (let k = 0; k < N; k++) {
        const px0 = (hash(k * 13 + 1) - 0.5) * 9;
        const ph = 0.15 + hash(k * 13 + 2) * 1.6;
        const zz = ((((hash(k * 13 + 3) * span - pos) % span) + span) % span) + Z_NEAR;
        const s = FOCAL / zz;
        const sx = W / 2 + (px0 - camX) * s;
        const sy = hy + (camH - ph) * s;
        const s2 = FOCAL / (zz + vel * shutter * 1.4);
        const qx = W / 2 + (px0 - camX) * s2;
        const qy = hy + (camH - ph) * s2;
        const a =
          Math.min(1, (vel - 3) / 25) * (1 - smooth(8, span, zz)) * smooth(0.6, 2.5, zz) * 0.75;
        if (a <= 0.01) continue;
        ctx.globalAlpha = fade * a;
        ctx.strokeStyle = k % 3 === 0 ? "rgba(212,167,124,1)" : "rgba(250,248,244,1)";
        ctx.lineWidth = Math.min(4, Math.max(1, 0.012 * s));
        ctx.beginPath();
        ctx.moveTo(qx, qy);
        ctx.lineTo(sx, sy);
        ctx.stroke();
      }
    }

    ctx.globalAlpha = fade;
    // neblina no horizonte
    const fogG = ctx.createLinearGradient(0, hy - 4, 0, hy + 130);
    fogG.addColorStop(0, "rgba(11,31,75,0.9)");
    fogG.addColorStop(1, "rgba(11,31,75,0)");
    ctx.fillStyle = fogG;
    ctx.fillRect(0, hy - 4, W, 134);
    // linha fina do horizonte, por cima da neblina
    ctx.fillStyle = `rgba(${gc[0]},${gc[1]},${gc[2]},${Math.min(0.85, glowA * 1.5)})`;
    ctx.fillRect(0, hy - 1, W, 2);
    ctx.globalAlpha = 1;
  }

  window.BTField = { draw: draw, hash: hash, smooth: smooth };
})();
