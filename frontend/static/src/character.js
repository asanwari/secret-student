export const CHARACTER_FRAME = { width: 32, height: 48 };
export const CHARACTER_LAYERS = ["gear-back", "body", "pants", "shirt", "hair", "gear-front"];
export const APPEARANCE_COLORS = {
  shirt: { red: 0xd94b48, blue: 0x3f71b5, green: 0x4d8d59, yellow: 0xe1b840, purple: 0x765495, teal: 0x398b87 },
  pants: { navy: 0x263b60, charcoal: 0x3d4148, brown: 0x6f4d3b, olive: 0x5d673f, blue: 0x365f86, plum: 0x61405d },
  hair: { black: 0x1d2025, dark_brown: 0x3b271f, brown: 0x70462c, blond: 0xc99a45, auburn: 0x8a3f2c },
};

const DIRECTIONS = { down: 0, left: 1, right: 2, up: 3 };
const TINTED_LAYERS = { pants: "pants", shirt: "shirt", hair: "hair" };
const DEFAULT_APPEARANCE = { shirt: "red", pants: "navy", hair: "dark_brown" };
const colorName = (palette, appearance) => {
  const selected = appearance[`${palette}_color`];
  return Object.hasOwn(APPEARANCE_COLORS[palette], selected) ? selected : DEFAULT_APPEARANCE[palette];
};
export const characterAssetUrl = (layer, appearance = {}) => {
  const palette = TINTED_LAYERS[layer];
  const suffix = palette ? `-${colorName(palette, appearance)}` : "";
  return `/game-static/assets/player/student-${layer}${suffix}.png`;
};

export function preloadCharacter(scene, appearance = {}) {
  CHARACTER_LAYERS.forEach((layer) => {
    scene.load.spritesheet(`student-${layer}`, characterAssetUrl(layer, appearance), { frameWidth: CHARACTER_FRAME.width, frameHeight: CHARACTER_FRAME.height });
  });
}

export function createCharacter(scene, x, y, appearance = {}) {
  const container = scene.add.container(x, y);
  const shadow = scene.add.ellipse(0, 1, 24, 8, 0x17202a, .28);
  const sprites = CHARACTER_LAYERS.map((layer) => {
    const sprite = scene.add.sprite(0, -24, `student-${layer}`, 1).setOrigin(.5, .5);
    return sprite;
  });
  container.add([shadow, ...sprites]);
  return { container, sprites, facing: "down", moving: false };
}

export function resolveCharacterFacing(dx, dy, current = "down") {
  if (!dx && !dy) return current;
  const horizontal = dx < 0 ? "left" : "right";
  const vertical = dy < 0 ? "up" : "down";
  if (Math.abs(dx) > Math.abs(dy)) return horizontal;
  if (Math.abs(dy) > Math.abs(dx)) return vertical;
  return current === "left" || current === "right" ? horizontal : vertical;
}

export function updateCharacter(rig, dx, dy, time) {
  const moving = Boolean(dx || dy);
  rig.facing = resolveCharacterFacing(dx, dy, rig.facing);
  rig.moving = moving;
  const column = moving ? [0, 1, 2, 1][Math.floor(time / 125) % 4] : 1;
  const frame = DIRECTIONS[rig.facing] * 3 + column;
  rig.sprites.forEach((sprite) => sprite.setFrame(frame));
}

const previewImages = new Map();
const previewDrawIds = new WeakMap();

function loadPreviewImages(appearance) {
  const urls = CHARACTER_LAYERS.map((layer) => [layer, characterAssetUrl(layer, appearance)]);
  const key = urls.map(([, url]) => url).join("|");
  if (!previewImages.has(key)) {
    previewImages.set(key, Promise.all(urls.map(([layer, url]) => new Promise((resolve, reject) => {
      const image = new Image();
      image.onload = () => resolve([layer, image]);
      image.onerror = reject;
      image.src = url;
    }))).then(Object.fromEntries));
  }
  return previewImages.get(key);
}

export async function drawCharacterPreview(canvas, appearance = {}) {
  const drawId = (previewDrawIds.get(canvas) || 0) + 1;
  previewDrawIds.set(canvas, drawId);
  const images = await loadPreviewImages(appearance);
  if (previewDrawIds.get(canvas) !== drawId) return;
  const context = canvas.getContext("2d");
  context.imageSmoothingEnabled = false;
  context.clearRect(0, 0, canvas.width, canvas.height);
  for (const layer of CHARACTER_LAYERS) {
    context.drawImage(images[layer], CHARACTER_FRAME.width, 0, CHARACTER_FRAME.width, CHARACTER_FRAME.height, 0, 0, CHARACTER_FRAME.width, CHARACTER_FRAME.height);
  }
}
