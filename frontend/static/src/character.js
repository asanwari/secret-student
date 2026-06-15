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
const assetUrl = (layer) => `/game-static/assets/player/student-${layer}.png`;

export function preloadCharacter(scene) {
  CHARACTER_LAYERS.forEach((layer) => {
    scene.load.spritesheet(`student-${layer}`, assetUrl(layer), { frameWidth: CHARACTER_FRAME.width, frameHeight: CHARACTER_FRAME.height });
  });
}

export function createCharacter(scene, x, y, appearance = {}) {
  const container = scene.add.container(x, y);
  const shadow = scene.add.ellipse(0, 1, 24, 8, 0x17202a, .28);
  const sprites = CHARACTER_LAYERS.map((layer) => {
    const sprite = scene.add.sprite(0, -24, `student-${layer}`, 1).setOrigin(.5, .5);
    const palette = TINTED_LAYERS[layer];
    if (palette) sprite.setTint(APPEARANCE_COLORS[palette][appearance[`${palette}_color`]] || APPEARANCE_COLORS[palette][DEFAULT_APPEARANCE[palette]]);
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

let previewImages = null;

function loadPreviewImages() {
  if (!previewImages) {
    previewImages = Promise.all(CHARACTER_LAYERS.map((layer) => new Promise((resolve, reject) => {
      const image = new Image();
      image.onload = () => resolve([layer, image]);
      image.onerror = reject;
      image.src = assetUrl(layer);
    }))).then(Object.fromEntries);
  }
  return previewImages;
}

function colorHex(value) {
  return `#${value.toString(16).padStart(6, "0")}`;
}

function drawTintedFrame(context, image, tint, x, y) {
  const buffer = document.createElement("canvas");
  buffer.width = CHARACTER_FRAME.width;
  buffer.height = CHARACTER_FRAME.height;
  const bufferContext = buffer.getContext("2d");
  bufferContext.imageSmoothingEnabled = false;
  bufferContext.drawImage(image, CHARACTER_FRAME.width, 0, CHARACTER_FRAME.width, CHARACTER_FRAME.height, 0, 0, CHARACTER_FRAME.width, CHARACTER_FRAME.height);
  bufferContext.globalCompositeOperation = "multiply";
  bufferContext.fillStyle = colorHex(tint);
  bufferContext.fillRect(0, 0, CHARACTER_FRAME.width, CHARACTER_FRAME.height);
  bufferContext.globalCompositeOperation = "destination-in";
  bufferContext.drawImage(image, CHARACTER_FRAME.width, 0, CHARACTER_FRAME.width, CHARACTER_FRAME.height, 0, 0, CHARACTER_FRAME.width, CHARACTER_FRAME.height);
  context.drawImage(buffer, x, y);
}

export async function drawCharacterPreview(canvas, appearance = {}) {
  const images = await loadPreviewImages();
  const context = canvas.getContext("2d");
  context.imageSmoothingEnabled = false;
  context.clearRect(0, 0, canvas.width, canvas.height);
  for (const layer of CHARACTER_LAYERS) {
    const palette = TINTED_LAYERS[layer];
    if (palette) {
      const tint = APPEARANCE_COLORS[palette][appearance[`${palette}_color`]] || APPEARANCE_COLORS[palette][DEFAULT_APPEARANCE[palette]];
      drawTintedFrame(context, images[layer], tint, 0, 0);
    } else {
      context.drawImage(images[layer], CHARACTER_FRAME.width, 0, CHARACTER_FRAME.width, CHARACTER_FRAME.height, 0, 0, CHARACTER_FRAME.width, CHARACTER_FRAME.height);
    }
  }
}
