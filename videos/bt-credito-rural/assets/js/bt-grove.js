/* Bananal em WebGL2, funcao pura do tempo e da camera (render deterministico).
 * Anatomia (referencias do cliente): pseudocaule manchado formado por bainhas, roseta de folhas
 * longas com nervura central clara, limbo com nervuras laterais paralelas e rasgos de vento,
 * folha-bandeira enrolada no topo, folhas velhas amarelando, folhas secas penduradas no
 * pseudocaule, mudas (filhos) na base, cachos verdes com coracao roxo, palhada no solo e linha
 * de microaspersores. Plantio em fileiras de 3,5 m. Unidades em metros, Y para cima, fileiras
 * ao longo de Z. Sem Math.random: todo acaso vem de um PRNG com semente fixa.
 */
(function () {
  "use strict";

  // ------------------------------------------------------------------ PRNG e matrizes
  function prng(seed) {
    let a = seed >>> 0;
    return function () {
      a = (a + 0x6d2b79f5) >>> 0;
      let t = Math.imul(a ^ (a >>> 15), 1 | a);
      t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
      return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
    };
  }
  function norm(v) {
    const l = Math.hypot(v[0], v[1], v[2]) || 1;
    return [v[0] / l, v[1] / l, v[2] / l];
  }
  function cross(a, b) {
    return [a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0]];
  }
  function sub(a, b) {
    return [a[0] - b[0], a[1] - b[1], a[2] - b[2]];
  }
  function dot(a, b) {
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2];
  }
  function perspective(fovy, aspect, near, far) {
    const f = 1 / Math.tan(fovy / 2);
    const nf = 1 / (near - far);
    return [
      f / aspect,
      0,
      0,
      0,
      0,
      f,
      0,
      0,
      0,
      0,
      (far + near) * nf,
      -1,
      0,
      0,
      2 * far * near * nf,
      0,
    ];
  }
  function lookAt(eye, target, up) {
    const z = norm(sub(eye, target));
    const x = norm(cross(up, z));
    const y = cross(z, x);
    return [
      x[0],
      y[0],
      z[0],
      0,
      x[1],
      y[1],
      z[1],
      0,
      x[2],
      y[2],
      z[2],
      0,
      -dot(x, eye),
      -dot(y, eye),
      -dot(z, eye),
      1,
    ];
  }
  function mul(a, b) {
    const o = new Array(16);
    for (let c = 0; c < 4; c++)
      for (let r = 0; r < 4; r++) {
        let s = 0;
        for (let k = 0; k < 4; k++) s += a[k * 4 + r] * b[c * 4 + k];
        o[c * 4 + r] = s;
      }
    return o;
  }

  // ------------------------------------------------------------------ GLSL compartilhado
  const COMMON = `
precision highp float;
uniform vec3 u_eye;
uniform vec3 u_sun;
uniform vec3 u_sunCol;
uniform vec3 u_zenith;
uniform vec3 u_horizon;
uniform vec3 u_ambUp;
uniform vec3 u_ambDn;
uniform float u_fogD;
uniform float u_exposure;
uniform float u_sat;
uniform float u_red;
uniform float u_split;
uniform int u_mode;
uniform float u_time;
float h1(float n) { return fract(sin(n * 127.1) * 43758.5453); }
float h2(vec2 p) { return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453); }
float vnoise(vec2 p) {
  vec2 i = floor(p), f = fract(p);
  vec2 w = f * f * (3.0 - 2.0 * f);
  float a = h2(i), b = h2(i + vec2(1, 0)), c = h2(i + vec2(0, 1)), d = h2(i + vec2(1, 1));
  return mix(mix(a, b, w.x), mix(c, d, w.x), w.y);
}
float fbm(vec2 p) {
  float s = 0.0, a = 0.5;
  for (int i = 0; i < 4; i++) { s += a * vnoise(p); p = p * 2.03 + 17.1; a *= 0.5; }
  return s;
}
// sombra falsa do dossel: abaixo das copas e longe do eixo da entrelinha a luz direta cai,
// com manchas de luz filtrada pelas folhas
float sunVis(vec3 p) {
  float h = smoothstep(1.0, 4.0, p.y);
  float dap = smoothstep(0.42, 0.58, vnoise(p.xz * 0.85 + vec2(p.y * 0.6, p.y * 0.3)));
  return clamp((0.12 + 0.88 * h) * mix(0.3, 1.0, dap), 0.0, 1.0);
}
vec3 skyCol(vec3 d) {
  float y = clamp(d.y, -0.3, 1.0);
  float sd = max(dot(d, u_sun), 0.0);
  vec3 hor = u_horizon * (0.85 + 0.25 * pow(sd, 4.0));
  vec3 c = mix(hor, u_zenith, pow(max(y, 0.0), 0.42));
  c += u_sunCol * (0.14 * pow(sd, 24.0) + 0.6 * pow(sd, 1400.0));
  return c;
}
float g_fog = 0.0;
uniform float u_fogAlpha;
vec3 fogIt(vec3 c, vec3 p) {
  vec3 d = p - u_eye;
  float dist = length(d);
  vec3 dir = d / max(dist, 1e-4);
  float f = 1.0 - exp(-dist * u_fogD);
  f = clamp(f + 0.12 * f * exp(-max(p.y, 0.0) * 0.6), 0.0, 1.0);
  vec3 fc = skyCol(normalize(vec3(dir.x, max(dir.y, 0.0) * 0.25 + 0.015, dir.z)));
  g_fog = f;
  // modo transparente: a distancia se dissolve no fundo da composicao (DOM)
  if (u_fogAlpha > 0.5) return mix(c, fc, f * 0.35);
  return mix(c, fc, f);
}
vec3 grade(vec3 c) {
  c *= u_exposure;
  c = (c * (2.51 * c + 0.03)) / (c * (2.43 * c + 0.59) + 0.14);
  float l = dot(c, vec3(0.2126, 0.7152, 0.0722));
  c = mix(vec3(l), c, u_sat);
  vec3 navy = vec3(0.012, 0.03, 0.075);
  c = c + navy * (1.0 - c) * 0.2;
  vec3 redc = vec3(l * 1.25 + 0.03, l * 0.32, l * 0.36);
  c = mix(c, redc, u_red);
  return pow(clamp(c, 0.0, 1.0), vec3(1.0 / 2.2));
}
vec4 outC(vec3 c) {
  vec3 g = grade(c);
  if (u_fogAlpha > 0.5) {
    float a = 1.0 - g_fog;
    return vec4(g * a, a);
  }
  return vec4(g, 1.0);
}
`;

  const FRAG = `
// divisao de foco: camada distante (nitida) e camada rente a lente (desfocada via CSS)
void splitTest(vec3 p) {
  if (u_mode == 0) return;
  float dist = length(p - u_eye);
  float dz = h2(gl_FragCoord.xy) * 0.8 - 0.4;
  if (u_mode == 1 && dist < u_split + dz) discard;
  if (u_mode == 2 && dist > u_split + dz) discard;
}
`;

  // ------------------------------------------------------------------ folhas
  const LEAF_VS = `#version 300 es
${COMMON}
layout(location = 0) in vec2 a_uv;
layout(location = 1) in vec4 i_a;
layout(location = 2) in vec4 i_b;
layout(location = 3) in vec4 i_c;
uniform mat4 u_vp;
out vec2 v_uv;
out vec3 v_pos;
out vec3 v_n;
out vec3 v_top;
out vec4 v_c;
out float v_t;
out float v_L;
const float PF = 0.15;
void main() {
  float u = a_uv.x, v = a_uv.y, av = abs(v);
  float L = i_a.w, seed = i_c.x, tear = i_c.z, fold = i_c.w;
  float sway = 1.0 - step(2.5, i_c.y);
  float az = i_b.x + sway * 0.03 * sin(u_time * 1.3 + seed * 17.0) * u;
  float th0 = i_b.y + sway * 0.035 * sin(u_time * 1.7 + seed * 29.0) * u;
  float droop = i_b.z;
  float k = max(droop, 0.002) / L;
  float s = u * L;
  float th = th0 - k * s;
  float x = (sin(th0) - sin(th)) / k;
  float y = (cos(th) - cos(th0)) / k;
  float td = droop * 0.16 * L;
  y -= td * u * u * u;
  vec3 hd = vec3(sin(az), 0.0, cos(az));
  vec3 side = vec3(cos(az), 0.0, -sin(az));
  vec3 up = vec3(0.0, 1.0, 0.0);
  vec3 T = normalize(hd * cos(th) + up * (sin(th) - 3.0 * td * u * u / L));
  vec3 N = normalize(cross(T, side));
  float t = clamp((u - PF) / (1.0 - PF), 0.0, 1.0);
  float W = i_b.w;
  float w = u < PF ? 0.024 * (1.0 - 0.3 * u / PF) : W * pow(max(sin(3.14159 * t), 0.0), 0.36) + 0.02 * (1.0 - t);
  float curl = 0.32 * (0.4 + 0.6 * t);
  vec3 P = vec3(i_a.xyz) + hd * x + up * y;
  vec3 off = side * v * w + N * (fold * av * w * 0.55 - curl * v * v * w);
  // tiras rasgadas pelo vento caem com o peso
  float nb = 10.0 + floor(h1(seed) * 7.0);
  float q = t * nb - av * 1.35;
  float bid = floor(q);
  float depth = tear * (0.2 + 0.8 * h1(bid * 3.1 + seed * 7.0));
  float e = max(0.0, av - (1.0 - depth));
  off.y -= e * w * (0.5 + 1.1 * h1(bid * 5.7 + seed)) * tear * 1.3;
  off += N * sin(t * L * 26.0 + seed) * 0.006 * av;
  P += off;
  float sg = v < 0.0 ? -1.0 : 1.0;
  vec3 dPdv = side * w + N * (fold * sg * w * 0.55 - 2.0 * curl * v * w);
  v_n = normalize(cross(T, dPdv));
  v_top = N;
  v_uv = a_uv;
  v_pos = P;
  v_c = i_c;
  v_t = t;
  v_L = L;
  gl_Position = u_vp * vec4(P, 1.0);
}`;

  const LEAF_FS = `#version 300 es
${COMMON}
${FRAG}
in vec2 v_uv;
in vec3 v_pos;
in vec3 v_n;
in vec3 v_top;
in vec4 v_c;
in float v_t;
in float v_L;
out vec4 o;
const float PF = 0.15;
void main() {
  splitTest(v_pos);
  float u = v_uv.x, v = v_uv.y, av = abs(v), t = v_t;
  float seed = v_c.x, age = v_c.y, tear = v_c.z;
  // rasgos de vento: cortes ao longo das nervuras laterais, da borda para a nervura central
  if (u > PF) {
    float nb = 10.0 + floor(h1(seed) * 7.0);
    float q = t * nb - av * 1.35;
    float bid = floor(q);
    float f = fract(q);
    float depth = tear * (0.2 + 0.8 * h1(bid * 3.1 + seed * 7.0));
    float e = av - (1.0 - depth);
    if (e > 0.0) {
      float gap = 0.015 + 0.09 * e / max(depth, 1e-3);
      if (f < gap) discard;
    }
    // borda irregular e ponta arredondada levemente gasta
    float rag = 0.99 - 0.035 * vnoise(vec2(t * 22.0, seed * 9.0)) * (0.3 + age * 0.3);
    if (av > rag) discard;
    // pequenos furos e falhas nas folhas velhas e secas
    if (age > 2.5 && vnoise(vec2(t * 9.0 + seed, av * 2.5)) > 0.8) discard;
  }
  vec3 V = normalize(u_eye - v_pos);
  vec3 n = normalize(v_n);
  if (!gl_FrontFacing) n = -n;
  bool under = dot(n, v_top) < 0.0;
  if (dot(n, V) < 0.0) n = -n;

  // cor do limbo pela idade: jovem verde-amarelado, adulta verde intensa, velha amarelando, seca palha
  vec3 young = vec3(0.30, 0.50, 0.10);
  vec3 adult = vec3(0.13, 0.30, 0.07);
  vec3 old = vec3(0.3, 0.33, 0.09);
  vec3 dry = vec3(0.17, 0.11, 0.06);
  vec3 alb = age < 1.0 ? mix(young, adult, age) : age < 2.0 ? mix(adult, old, age - 1.0) : mix(old, dry, clamp(age - 2.0, 0.0, 1.0));
  float mott = fbm(vec2(t * v_L * 3.0 + seed * 5.0, v * 2.0));
  alb *= 0.82 + 0.36 * mott;
  // mais claro perto da nervura central, mais escuro na borda
  alb *= 1.12 - 0.2 * av;
  // nervuras laterais paralelas, finas e densas
  float vq = fract(t * v_L * 55.0 - av * 2.6 + seed);
  alb *= 0.93 + 0.1 * smoothstep(0.7, 1.0, vq);
  // necrose marrom na borda e manchas nas folhas adultas e velhas
  float edgeN = smoothstep(0.86 - 0.12 * vnoise(vec2(t * 18.0, seed)), 1.0, av) * clamp(age - 0.6, 0.0, 1.0);
  alb = mix(alb, vec3(0.22, 0.14, 0.07), edgeN * 0.85);
  float spot = age > 2.5 ? 0.0 : smoothstep(0.86, 0.9, vnoise(vec2(t * v_L * 160.0 + seed * 3.0, v * 30.0))) * clamp(age - 0.9, 0.0, 0.6);
  alb = mix(alb, vec3(0.12, 0.09, 0.05), spot * 0.7);
  if (age > 2.0) alb = mix(alb, vec3(0.34, 0.25, 0.14), smoothstep(0.45, 0.85, fbm(vec2(t * 30.0, v * 1.5 + seed))) * 0.6);
  // pecíolo e nervura central claros
  float rib = u < PF ? 1.0 : 1.0 - smoothstep(0.022, 0.05, av);
  alb = mix(alb, age > 2.0 ? vec3(0.38, 0.3, 0.17) : vec3(0.42, 0.5, 0.2), rib * 0.85);
  if (under) alb = mix(alb, vec3(dot(alb, vec3(0.33))) * vec3(0.95, 1.05, 1.0), 0.35) * 1.12;

  float ndl = dot(n, u_sun);
  float wrap = max((ndl + 0.3) / 1.3, 0.0);
  vec3 amb = mix(u_ambDn, u_ambUp, n.y * 0.5 + 0.5);
  float sv = sunVis(v_pos);
  vec3 col = alb * (amb * (0.5 + 0.5 * sv) + u_sunCol * wrap * 0.75 * sv);
  // translucidez: folha contra a luz acende em verde-amarelo
  float back = max(0.0, -ndl);
  float fwd = pow(max(dot(-V, u_sun), 0.0), 3.0);
  vec3 trans = alb * vec3(1.25, 1.35, 0.55) * (age > 2.5 ? 0.35 : 1.0);
  col += trans * u_sunCol * back * (0.25 + 1.3 * fwd) * (0.25 + 0.75 * sv);
  // brilho ceroso
  vec3 H = normalize(u_sun + V);
  col += u_sunCol * pow(max(dot(n, H), 0.0), 48.0) * 0.22 * sv * (1.0 - edgeN) * (age > 2.5 ? 0.2 : 1.0);
  col = fogIt(col, v_pos);
  o = outC(col);
}`;

  // ------------------------------------------------------------------ pseudocaules, aspersores e cachos
  const STEM_VS = `#version 300 es
${COMMON}
layout(location = 0) in vec2 a_uv;
layout(location = 1) in vec4 i_a;
layout(location = 2) in vec4 i_b;
uniform mat4 u_vp;
out vec3 v_pos;
out vec3 v_n;
out vec2 v_uv;
out vec4 v_b;
// raio do cacho em funcao do angulo e da posicao ao longo do eixo pendente
float bunchR(float a, float q) {
  float b = q / 0.6;
  float hi = floor(b * 7.0);
  float cx = a / 6.28318 * 11.0 + 0.5 * mod(hi, 2.0);
  float fx = fract(cx) - 0.5;
  float fy = fract(b * 7.0);
  float finger = sqrt(max(0.0, 1.0 - pow(fx / 0.46, 2.0))) * smoothstep(0.0, 0.3, fy) * (1.0 - 0.35 * smoothstep(0.75, 1.0, fy));
  float bunch = q < 0.6 ? (0.19 - 0.07 * b) * smoothstep(0.0, 0.06, b) * (0.62 + 0.38 * finger + 0.12 * fy) : 0.0;
  float bq = (q - 0.78) / 0.22;
  float bud = q > 0.78 ? 0.075 * pow(max(sin(3.14159 * min(bq * 0.9 + 0.1, 1.0)), 0.0), 0.7) : 0.0;
  return max(max(bunch, bud), 0.018);
}
void main() {
  float a = a_uv.x * 6.28318, hh = a_uv.y;
  float H = i_a.w, kind = i_b.w;
  float r = mix(i_b.x, i_b.y, hh);
  vec3 axis = vec3(0.0, 1.0, 0.0);
  vec3 base = i_a.xyz;
  vec3 P;
  vec3 N;
  if (kind < 0.5) {
    // pseudocaule: base alargada, leve inclinacao, bainhas sobrepostas
    r *= 1.0 + 0.35 * exp(-hh * 9.0) + 0.04 * sin(a * 3.0 + i_b.z * 10.0) * (1.0 - hh);
    float lean = (h1(i_b.z * 11.0) - 0.5) * 0.18;
    float lean2 = (h1(i_b.z * 13.0) - 0.5) * 0.18;
    P = base + vec3(cos(a) * r + lean * hh * hh * H, hh * H, sin(a) * r + lean2 * hh * hh * H);
    N = normalize(vec3(cos(a), 0.12, sin(a)));
  } else if (kind < 1.5) {
    // estaca do microaspersor com bocal azul
    float capR = hh > 0.88 ? 0.022 : r;
    P = base + vec3(cos(a) * capR, hh * H, sin(a) * capR);
    N = vec3(cos(a), 0.0, sin(a));
  } else {
    // cacho: engaco sai do topo e curva para fora, cacho pendente (pencas em aneis), raquis e coracao
    vec3 outd = vec3(sin(i_b.z * 6.28318), 0.0, cos(i_b.z * 6.28318));
    vec3 c;
    vec3 tng;
    float rr;
    if (hh < 0.2) {
      float q = hh / 0.2;
      float ang = q * 1.5708;
      c = base + outd * (0.42 * sin(ang)) + vec3(0.0, 0.18 * (1.0 - cos(ang)) * -1.0 + 0.05 * sin(ang), 0.0);
      tng = normalize(outd * cos(ang) - vec3(0.0, sin(ang), 0.0));
      rr = 0.028;
    } else {
      float q = (hh - 0.2) / 0.8;
      c = base + outd * 0.42 + vec3(0.0, -0.13 - q * H, 0.0);
      tng = vec3(0.0, -1.0, 0.0);
      rr = bunchR(a, q);
    }
    vec3 sx = normalize(cross(tng, abs(tng.y) > 0.9 ? outd : vec3(0.0, 1.0, 0.0)));
    vec3 sy = normalize(cross(sx, tng));
    vec3 R0 = sx * cos(a) + sy * sin(a);
    P = c + R0 * rr;
    N = R0;
    if (hh >= 0.2) {
      float q = (hh - 0.2) / 0.8;
      float da = 0.03, dq = 0.003;
      vec3 Ta = (-sx * sin(a) + sy * cos(a)) * rr + R0 * (bunchR(a + da, q) - rr) / da;
      vec3 Tq = tng * H + R0 * (bunchR(a, q + dq) - rr) / dq;
      N = normalize(cross(Ta, Tq));
      if (dot(N, R0) < 0.0) N = -N;
    }
  }
  v_pos = P;
  v_n = N;
  v_uv = a_uv;
  v_b = i_b;
  gl_Position = u_vp * vec4(P, 1.0);
}`;

  const STEM_FS = `#version 300 es
${COMMON}
${FRAG}
in vec3 v_pos;
in vec3 v_n;
in vec2 v_uv;
in vec4 v_b;
out vec4 o;
void main() {
  splitTest(v_pos);
  vec3 V = normalize(u_eye - v_pos);
  vec3 n = normalize(v_n);
  float kind = v_b.w, seed = v_b.z;
  vec3 alb;
  float gloss = 0.0;
  if (kind < 0.5) {
    float a = v_uv.x, hh = v_uv.y;
    // bainhas: faixas verticais em leve espiral
    float sheath = fract(a * 5.0 + hh * 0.6 + seed);
    vec3 green = vec3(0.16, 0.24, 0.07);
    vec3 brown = vec3(0.16, 0.1, 0.05);
    float m = fbm(vec2(a * 9.0 + seed * 3.0, hh * 4.0));
    alb = mix(green, brown, smoothstep(0.35, 0.75, m) * (0.5 + 0.5 * (1.0 - hh)));
    // manchas escuras alongadas caracteristicas do pseudocaule
    float blot = smoothstep(0.62, 0.7, fbm(vec2(a * 14.0 + seed * 7.0, hh * 30.0)));
    alb = mix(alb, vec3(0.05, 0.045, 0.03), blot * 0.85);
    // bainhas secas descascando na parte baixa
    float peel = smoothstep(0.55, 0.62, vnoise(vec2(a * 6.0 + seed, hh * 3.0))) * (1.0 - smoothstep(0.35, 0.7, hh));
    alb = mix(alb, vec3(0.42, 0.33, 0.2), peel * 0.8);
    alb *= 0.85 + 0.25 * smoothstep(0.0, 0.08, sheath) * (1.0 - smoothstep(0.92, 1.0, sheath));
    alb *= 0.9 + 0.2 * fract(sin(hh * 400.0 + a * 50.0) * 43.0) * 0.5;
    gloss = 0.08;
  } else if (kind < 1.5) {
    alb = v_uv.y > 0.88 ? vec3(0.03, 0.12, 0.42) : vec3(0.06, 0.06, 0.06);
    gloss = 0.3;
  } else {
    float q = (v_uv.y - 0.2) / 0.8;
    float b = q / 0.6;
    float fy = fract(b * 7.0);
    float ring = smoothstep(0.0, 0.25, fy) * (1.0 - 0.4 * smoothstep(0.8, 1.0, fy));
    alb = vec3(0.3, 0.48, 0.1) * (0.55 + 0.6 * ring) * (0.85 + 0.3 * vnoise(vec2(v_uv.x * 40.0, v_uv.y * 120.0)));
    if (v_uv.y < 0.2 || (q > 0.6 && q < 0.78)) alb = vec3(0.26, 0.28, 0.12);
    if (q > 0.78) alb = vec3(0.4, 0.07, 0.15) * (0.8 + 0.4 * vnoise(vec2(v_uv.x * 20.0, v_uv.y * 60.0)));
    gloss = 0.25;
  }
  float ndl = dot(n, u_sun);
  vec3 amb = mix(u_ambDn, u_ambUp, n.y * 0.5 + 0.5);
  float sv = kind > 1.5 ? max(sunVis(v_pos), 0.55) : sunVis(v_pos);
  vec3 col = alb * (amb * (0.45 + 0.55 * sv) + u_sunCol * max((ndl + 0.25) / 1.25, 0.0) * 0.7 * sv);
  float rim = pow(1.0 - max(dot(n, V), 0.0), 3.0) * max(dot(-V, u_sun) + 0.3, 0.0);
  col += u_sunCol * rim * 0.35 * alb * 3.0 * (0.3 + 0.7 * sv);
  vec3 H = normalize(u_sun + V);
  col += u_sunCol * pow(max(dot(n, H), 0.0), 30.0) * gloss;
  col = fogIt(col, v_pos);
  o = outC(col);
}`;

  // ------------------------------------------------------------------ solo
  const GROUND_VS = `#version 300 es
${COMMON}
layout(location = 0) in vec2 a_p;
uniform mat4 u_vp;
uniform vec4 u_gr;
out vec3 v_pos;
void main() {
  vec3 P = vec3(u_gr.x + a_p.x * u_gr.z, 0.0, u_gr.y + a_p.y * u_gr.w);
  v_pos = P;
  gl_Position = u_vp * vec4(P, 1.0);
}`;
  const GROUND_FS = `#version 300 es
${COMMON}
${FRAG}
in vec3 v_pos;
uniform float u_rowSp;
uniform float u_rowOff;
out vec4 o;
void main() {
  splitTest(v_pos);
  vec2 p = v_pos.xz;
  float rx = mod(p.x - u_rowOff + u_rowSp * 0.5, u_rowSp) - u_rowSp * 0.5;
  float nearRow = 1.0 - smoothstep(0.3, 1.3, abs(rx));
  vec3 soil = vec3(0.13, 0.085, 0.055) * (0.8 + 0.4 * fbm(p * 0.7));
  // palhada: pedacos de folha seca alongados em varias direcoes
  vec2 q = p * vec2(2.2, 0.9);
  float lit = smoothstep(0.52, 0.62, fbm(q + fbm(p * 1.3) * 1.5));
  float lit2 = smoothstep(0.55, 0.65, fbm(p.yx * vec2(2.6, 0.8) + 7.0));
  vec3 straw = vec3(0.34, 0.25, 0.14) * (0.75 + 0.5 * vnoise(p * 9.0));
  vec3 col = mix(soil, straw, clamp(lit + lit2, 0.0, 1.0) * (0.45 + 0.5 * nearRow));
  // capim baixo no meio da entrelinha
  float grass = smoothstep(0.5, 0.7, fbm(p * 1.6 + 3.0)) * (1.0 - nearRow) * 0.8;
  col = mix(col, vec3(0.09, 0.17, 0.05) * (0.7 + 0.6 * vnoise(p * 14.0)), grass);
  // mangueira de irrigacao ao pe da fileira
  float hose = 1.0 - smoothstep(0.012, 0.03, abs(rx - 0.32));
  col = mix(col, vec3(0.03, 0.03, 0.03), hose * 0.9);
  float shade = 0.55 + 0.45 * smoothstep(0.2, 1.6, abs(rx));
  vec3 lightC = u_ambUp * 1.6 + u_sunCol * 0.5 * shade * sunVis(v_pos + vec3(0.0, 1.2, 0.0)) ;
  col *= lightC;
  col = fogIt(col, v_pos);
  o = outC(col);
}`;

  // ------------------------------------------------------------------ ceu
  const SKY_VS = `#version 300 es
layout(location = 0) in vec2 a_p;
out vec2 v_p;
void main() { v_p = a_p; gl_Position = vec4(a_p, 0.9999, 1.0); }`;
  const SKY_FS = `#version 300 es
${COMMON}
${FRAG}
in vec2 v_p;
uniform vec3 u_cr;
uniform vec3 u_cu;
uniform vec3 u_cf;
uniform vec2 u_tan;
out vec4 o;
void main() {
  if (u_mode == 2) discard;
  vec3 d = normalize(u_cf + u_cr * v_p.x * u_tan.x + u_cu * v_p.y * u_tan.y);
  vec3 c = skyCol(d);
  o = vec4(grade(c), 1.0);
}`;

  // ------------------------------------------------------------------ montagem
  function compile(gl, vs, fs) {
    const mk = (type, src) => {
      const s = gl.createShader(type);
      gl.shaderSource(s, src);
      gl.compileShader(s);
      if (!gl.getShaderParameter(s, gl.COMPILE_STATUS))
        throw new Error("BTGrove shader: " + gl.getShaderInfoLog(s));
      return s;
    };
    const p = gl.createProgram();
    gl.attachShader(p, mk(gl.VERTEX_SHADER, vs));
    gl.attachShader(p, mk(gl.FRAGMENT_SHADER, fs));
    gl.linkProgram(p);
    if (!gl.getProgramParameter(p, gl.LINK_STATUS))
      throw new Error("BTGrove link: " + gl.getProgramInfoLog(p));
    const uni = {};
    const n = gl.getProgramParameter(p, gl.ACTIVE_UNIFORMS);
    for (let i = 0; i < n; i++) {
      const info = gl.getActiveUniform(p, i);
      uni[info.name] = gl.getUniformLocation(p, info.name);
    }
    return { p, uni };
  }

  function leafGrid(nu, nv) {
    const pts = [];
    for (let j = 0; j <= nv; j++)
      for (let i = 0; i <= nu; i++) pts.push(Math.pow(i / nu, 0.9), -1 + (2 * j) / nv);
    const idx = [];
    for (let j = 0; j < nv; j++)
      for (let i = 0; i < nu; i++) {
        const a = j * (nu + 1) + i;
        idx.push(a, a + 1, a + nu + 1, a + 1, a + nu + 2, a + nu + 1);
      }
    return { pts: new Float32Array(pts), idx: new Uint16Array(idx) };
  }
  function tubeGrid(na, nh) {
    const pts = [];
    for (let j = 0; j <= nh; j++) for (let i = 0; i <= na; i++) pts.push(i / na, j / nh);
    const idx = [];
    for (let j = 0; j < nh; j++)
      for (let i = 0; i < na; i++) {
        const a = j * (na + 1) + i;
        idx.push(a, a + na + 1, a + 1, a + 1, a + na + 1, a + na + 2);
      }
    return { pts: new Float32Array(pts), idx: new Uint16Array(idx) };
  }

  // ------------------------------------------------------------------ plantio
  // rows: posicoes X das fileiras; zFrom/zTo: extensao; extra: folhas extras (ex.: travessia na abertura)
  function buildGrove(seed, cfg) {
    const R = prng(seed);
    const leaves = [];
    const stems = [];
    const sp = cfg.spacing || 2.35;
    function addLeaf(base, L, az, th0, droop, W, age, tear, fold) {
      leaves.push(base[0], base[1], base[2], L, az, th0, droop, W, R() * 100, age, tear, fold);
    }
    function plant(x, z, scale, withBunch) {
      const H = (2.3 + R() * 1.0) * scale;
      const r0 = (0.13 + R() * 0.04) * Math.sqrt(scale);
      const sseed = R();
      stems.push(x, 0, z, H, r0, r0 * 0.62, sseed, 0);
      const nLeaf = scale < 0.5 ? 5 : 7 + Math.floor(R() * 4);
      const phase = R() * 6.283;
      for (let k = 0; k < nLeaf; k++) {
        const az = phase + k * 2.4 + (R() - 0.5) * 0.5;
        const f = k / (nLeaf - 1);
        const age = f < 0.2 ? 0.1 + R() * 0.3 : f < 0.8 ? 0.6 + R() * 0.5 : 1.3 + R() * 0.6;
        const th0 = 1.15 - 1.1 * f + (R() - 0.5) * 0.25;
        const droop = 0.35 + 1.05 * f + R() * 0.35;
        const L = (1.5 + R() * 0.7) * (k === 0 ? 0.75 : 1) * scale;
        const W = (0.27 + R() * 0.08) * scale;
        const tear = f < 0.2 ? R() * 0.15 : Math.min(1, 0.25 + R() * 0.65 + f * 0.25);
        const off = 0.04 * scale;
        addLeaf(
          [x + Math.sin(az) * off, H - 0.05 * scale * k, z + Math.cos(az) * off],
          L,
          az,
          th0,
          droop,
          W,
          age,
          tear,
          0.28 + R() * 0.25,
        );
      }
      // folha-bandeira enrolada no topo
      leaves.push(
        x,
        H,
        z,
        0.9 * scale,
        R() * 6.28,
        1.48,
        0.08,
        0.035 * scale,
        R() * 100,
        0.0,
        0.0,
        0.0,
      );
      // folhas secas penduradas no pseudocaule
      const nDead = scale < 0.5 ? 0 : 1 + Math.floor(R() * 3);
      for (let k = 0; k < nDead; k++) {
        const az = R() * 6.283;
        addLeaf(
          [x + Math.sin(az) * r0 * 0.7, H * (0.72 + R() * 0.2), z + Math.cos(az) * r0 * 0.7],
          (1.0 + R() * 0.6) * scale,
          az,
          -1.3 - R() * 0.2,
          0.12,
          0.075 * scale,
          3.0,
          1.0,
          0.9,
        );
      }
      if (withBunch) {
        const a = R();
        stems.push(x, H * 0.97, z, 1.25 * scale, 0.03, 0.03, a, 2);
      }
    }
    cfg.rows.forEach((rx, ri) => {
      for (let z = cfg.zFrom; z > cfg.zTo; z -= sp) {
        if (R() < 0.04) continue;
        const x = rx + (R() - 0.5) * 0.4;
        const zz = z + (R() - 0.5) * 0.7;
        const scale = 0.85 + R() * 0.3;
        plant(x, zz, scale, R() < (cfg.bunchP === undefined ? 0.3 : cfg.bunchP));
        // filho (muda) ao lado da planta mae
        if (R() < 0.45) {
          const a = R() * 6.28;
          plant(x + Math.cos(a) * 0.55, zz + Math.sin(a) * 0.55, 0.25 + R() * 0.2, false);
        }
        // microaspersor na linha de irrigacao
        if (cfg.sprinklers && Math.abs(rx) < 6 && R() < 0.55)
          stems.push(
            rx + (rx > 0 ? -1 : 1) * 0.9 + (R() - 0.5) * 0.2,
            0,
            zz + sp * 0.5,
            0.42,
            0.007,
            0.007,
            R(),
            1,
          );
      }
      void ri;
    });
    (cfg.extra || []).forEach((e) =>
      addLeaf(e.base, e.L, e.az, e.th0, e.droop, e.W, e.age, e.tear, e.fold || 0.35),
    );
    return { leaves: new Float32Array(leaves), stems: new Float32Array(stems) };
  }

  // ------------------------------------------------------------------ instancia
  function create(canvas, cfg) {
    const gl = canvas.getContext("webgl2", {
      antialias: cfg.antialias !== false,
      alpha: true,
      premultipliedAlpha: true,
      preserveDrawingBuffer: true,
    });
    if (!gl) throw new Error("BTGrove: WebGL2 indisponivel");
    const progs = {
      leaf: compile(gl, LEAF_VS, LEAF_FS),
      stem: compile(gl, STEM_VS, STEM_FS),
      ground: compile(gl, GROUND_VS, GROUND_FS),
      sky: compile(gl, SKY_VS, SKY_FS),
    };
    const data = buildGrove(cfg.seed || 7, cfg);
    const LEAF_STRIDE = 12;
    const STEM_STRIDE = 8;

    function geo(g) {
      const vbo = gl.createBuffer();
      gl.bindBuffer(gl.ARRAY_BUFFER, vbo);
      gl.bufferData(gl.ARRAY_BUFFER, g.pts, gl.STATIC_DRAW);
      const ibo = gl.createBuffer();
      gl.bindBuffer(gl.ELEMENT_ARRAY_BUFFER, ibo);
      gl.bufferData(gl.ELEMENT_ARRAY_BUFFER, g.idx, gl.STATIC_DRAW);
      return { vbo, ibo, count: g.idx.length };
    }
    const leafHi = geo(leafGrid(36, 10));
    const leafLo = geo(leafGrid(14, 4));
    const tubeHi = geo(tubeGrid(14, 16));
    const tubeLo = geo(tubeGrid(7, 6));
    const bunchGeo = geo(tubeGrid(66, 84));
    const quad = geo({
      pts: new Float32Array([-1, -1, 1, -1, 1, 1, -1, 1]),
      idx: new Uint16Array([0, 1, 2, 0, 2, 3]),
    });
    const unitQ = geo({
      pts: new Float32Array([0, 0, 1, 0, 1, 1, 0, 1]),
      idx: new Uint16Array([0, 1, 2, 0, 2, 3]),
    });
    const instBuf = gl.createBuffer();

    function bindGeo(g) {
      gl.bindBuffer(gl.ARRAY_BUFFER, g.vbo);
      gl.enableVertexAttribArray(0);
      gl.vertexAttribPointer(0, 2, gl.FLOAT, false, 0, 0);
      gl.bindBuffer(gl.ELEMENT_ARRAY_BUFFER, g.ibo);
    }
    function bindInst(arr, nvec4) {
      gl.bindBuffer(gl.ARRAY_BUFFER, instBuf);
      gl.bufferData(gl.ARRAY_BUFFER, arr, gl.DYNAMIC_DRAW);
      for (let k = 0; k < 3; k++) {
        const loc = 1 + k;
        if (k < nvec4) {
          gl.enableVertexAttribArray(loc);
          gl.vertexAttribPointer(loc, 4, gl.FLOAT, false, nvec4 * 16, k * 16);
          gl.vertexAttribDivisor(loc, 1);
        } else {
          gl.disableVertexAttribArray(loc);
        }
      }
    }
    function cull(src, stride, eye, fwd, maxD, nearD, wantNear) {
      const near = [];
      const far = [];
      for (let i = 0; i < src.length; i += stride) {
        const dx = src[i] - eye[0];
        const dz = src[i + 2] - eye[2];
        const along = dx * fwd[0] + dz * fwd[2];
        if (along < -4 || along > maxD) continue;
        const d = Math.hypot(dx, dz);
        if (Math.abs(dx * fwd[2] - dz * fwd[0]) > along * 1.2 + 6) continue;
        if (wantNear !== undefined && wantNear && d > nearD + 4) continue;
        const dst = d < nearD ? near : far;
        for (let k = 0; k < stride; k++) dst.push(src[i + k]);
      }
      return { near: new Float32Array(near), far: new Float32Array(far) };
    }
    function setCommon(pr, s) {
      const U = pr.uni;
      gl.uniform3fv(U.u_eye, s.eye);
      gl.uniform3fv(U.u_sun, s.sun);
      gl.uniform3fv(U.u_sunCol, s.sunCol);
      gl.uniform3fv(U.u_zenith, s.zenith);
      gl.uniform3fv(U.u_horizon, s.horizon);
      gl.uniform3fv(U.u_ambUp, s.ambUp);
      gl.uniform3fv(U.u_ambDn, s.ambDn);
      gl.uniform1f(U.u_fogD, s.fogD);
      gl.uniform1f(U.u_exposure, s.exposure);
      gl.uniform1f(U.u_sat, s.sat);
      gl.uniform1f(U.u_red, s.red);
      gl.uniform1f(U.u_split, s.split);
      gl.uniform1i(U.u_mode, s.mode);
      gl.uniform1f(U.u_time, s.time);
      gl.uniform1f(U.u_fogAlpha, s.fogAlpha ? 1 : 0);
      if (U.u_vp) gl.uniformMatrix4fv(U.u_vp, false, s.vp);
    }

    const DEF = {
      fov: 52,
      time: 0,
      mode: 0,
      split: 1.6,
      sun: [0.22, 0.1, -1],
      sunCol: [0.5, 0.36, 0.22],
      zenith: [0.002, 0.008, 0.03],
      horizon: [0.008, 0.02, 0.05],
      ambUp: [0.015, 0.025, 0.05],
      ambDn: [0.008, 0.008, 0.007],
      fogD: 0.024,
      exposure: 1.0,
      sat: 1.0,
      red: 0,
      maxD: 95,
      fogAlpha: false,
    };

    function render(o) {
      const s = Object.assign({}, DEF, o);
      s.sun = norm(s.sun);
      const W = canvas.width;
      const H = canvas.height;
      gl.viewport(0, 0, W, H);
      const aspect = W / H;
      const fovy = (s.fov * Math.PI) / 180;
      const view = lookAt(s.eye, s.target, s.up || [0, 1, 0]);
      const proj = perspective(fovy, aspect, 0.05, 220);
      s.vp = mul(proj, view);
      gl.clearColor(0, 0, 0, 0);
      gl.clear(gl.COLOR_BUFFER_BIT | gl.DEPTH_BUFFER_BIT);
      gl.enable(gl.DEPTH_TEST);
      gl.disable(gl.CULL_FACE);
      const fwd3 = norm(sub(s.target, s.eye));
      const fwd = norm([fwd3[0], 0, fwd3[2]]);

      // ceu (omitido no modo transparente: o fundo da composicao aparece)
      const sky = progs.sky;
      if (!s.fogAlpha) {
        gl.useProgram(sky.p);
        setCommon(sky, s);
        const cf = fwd3;
        const cr = norm(cross(cf, [0, 1, 0]));
        const cu = cross(cr, cf);
        gl.uniform3fv(sky.uni.u_cr, cr);
        gl.uniform3fv(sky.uni.u_cu, cu);
        gl.uniform3fv(sky.uni.u_cf, cf);
        gl.uniform2f(sky.uni.u_tan, Math.tan(fovy / 2) * aspect, Math.tan(fovy / 2));
        gl.depthMask(false);
        bindGeo(quad);
        for (let k = 1; k < 4; k++) gl.disableVertexAttribArray(k);
        gl.drawElements(gl.TRIANGLES, quad.count, gl.UNSIGNED_SHORT, 0);
        gl.depthMask(true);
      }

      // solo
      const gr = progs.ground;
      gl.useProgram(gr.p);
      setCommon(gr, s);
      gl.uniform4f(gr.uni.u_gr, s.eye[0] - 60, s.eye[2] - 160, 120, 180);
      gl.uniform1f(gr.uni.u_rowSp, cfg.rowSpacing || 3.5);
      gl.uniform1f(gr.uni.u_rowOff, cfg.rowOffset || 1.75);
      bindGeo(unitQ);
      gl.drawElements(gl.TRIANGLES, unitQ.count, gl.UNSIGNED_SHORT, 0);

      const wantNear = s.mode === 2 ? true : undefined;
      // pseudocaules, aspersores, cachos
      const st = progs.stem;
      gl.useProgram(st.p);
      setCommon(st, s);
      const sc = cull(data.stems, STEM_STRIDE, s.eye, fwd, s.maxD, 14, wantNear);
      const isBunch = (arr, yes) => {
        const out = [];
        for (let i = 0; i < arr.length; i += STEM_STRIDE)
          if (arr[i + 7] > 1.5 === yes) for (let k = 0; k < STEM_STRIDE; k++) out.push(arr[i + k]);
        return new Float32Array(out);
      };
      const bunches = new Float32Array([...isBunch(sc.near, true), ...isBunch(sc.far, true)]);
      [
        [isBunch(sc.near, false), tubeHi],
        [isBunch(sc.far, false), tubeLo],
        [bunches, bunchGeo],
      ].forEach(([arr, g]) => {
        if (!arr.length) return;
        bindGeo(g);
        bindInst(arr, 2);
        gl.drawElementsInstanced(
          gl.TRIANGLES,
          g.count,
          gl.UNSIGNED_SHORT,
          0,
          arr.length / STEM_STRIDE,
        );
      });

      // folhas
      const lf = progs.leaf;
      gl.useProgram(lf.p);
      setCommon(lf, s);
      const lc = cull(data.leaves, LEAF_STRIDE, s.eye, fwd, s.maxD, 16, wantNear);
      [
        [lc.near, leafHi],
        [lc.far, leafLo],
      ].forEach(([arr, g]) => {
        if (!arr.length) return;
        bindGeo(g);
        bindInst(arr, 3);
        gl.drawElementsInstanced(
          gl.TRIANGLES,
          g.count,
          gl.UNSIGNED_SHORT,
          0,
          arr.length / LEAF_STRIDE,
        );
      });
      for (let k = 1; k < 4; k++) gl.vertexAttribDivisor(k, 0);
    }
    return {
      render,
      gl,
      stats: { leaves: data.leaves.length / LEAF_STRIDE, stems: data.stems.length / STEM_STRIDE },
    };
  }

  // utilitarios deterministicos compartilhados pelas cenas
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

  window.BTGrove = { create, prng, hash, smooth };
})();
