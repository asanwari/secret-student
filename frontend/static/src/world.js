const WORLD_WIDTH = 960;
const WORLD_HEIGHT = 640;
const APPEARANCE_COLORS = {
  shirt: { red: 0xd94b48, blue: 0x3f71b5, green: 0x4d8d59, yellow: 0xe1b840, purple: 0x765495, teal: 0x398b87 },
  pants: { navy: 0x263b60, charcoal: 0x3d4148, brown: 0x6f4d3b, olive: 0x5d673f, blue: 0x365f86, plum: 0x61405d },
  hair: { black: 0x1d2025, dark_brown: 0x3b271f, brown: 0x70462c, blond: 0xc99a45, auburn: 0x8a3f2c },
};

function isEditableTarget(target) {
  return target instanceof HTMLElement && (
    target.matches("input, textarea, select, [contenteditable='true']") ||
    Boolean(target.closest("input, textarea, select, [contenteditable='true']"))
  );
}

export function createWorldController({
  mountId,
  getPlayerName,
  getPlayerAppearance,
  onNearbyChange,
  onEnterBuilding,
  initialPlayerPosition = null,
}) {
  let active = false;
  let player = null;
  let nearbyBuilding = null;
  let sceneRef = null;
  let savedPlayerPosition = initialPlayerPosition;
  const pressedKeys = new Set();

  // Phaser's keyboard plugin captures arrow/WASD keys at the browser level.
  // World-scoped DOM listeners avoid that global capture entirely, so normal
  // form fields keep every typing key when the player enters a building.
  function handleKeyDown(event) {
    if (!active || isEditableTarget(event.target) || isEditableTarget(document.activeElement)) return;
    const key = event.key.toLowerCase();
    if (["arrowleft", "arrowright", "arrowup", "arrowdown", "w", "a", "s", "d"].includes(key)) {
      pressedKeys.add(key);
      event.preventDefault();
    }
    if ((key === "enter" || key === " ") && nearbyBuilding) {
      event.preventDefault();
      enterNearby();
    }
  }

  function handleKeyUp(event) {
    pressedKeys.delete(event.key.toLowerCase());
  }

  window.addEventListener("keydown", handleKeyDown);
  window.addEventListener("keyup", handleKeyUp);
  window.addEventListener("blur", () => pressedKeys.clear());

  class WorldScene extends Phaser.Scene {
    constructor() { super("WorldScene"); }

    create() {
      sceneRef = this;
      drawMap(this);
      if (!active) this.scene.pause();
    }

    update() {
      if (!active || !player || isEditableTarget(document.activeElement)) return;
      const speed = 3.6;
      let dx = 0;
      let dy = 0;
      if (pressedKeys.has("arrowleft") || pressedKeys.has("a")) dx -= speed;
      if (pressedKeys.has("arrowright") || pressedKeys.has("d")) dx += speed;
      if (pressedKeys.has("arrowup") || pressedKeys.has("w")) dy -= speed;
      if (pressedKeys.has("arrowdown") || pressedKeys.has("s")) dy += speed;
      if (dx || dy) move(dx, dy);
    }
  }

  const game = new Phaser.Game({
    // The map only uses 2D primitives. Canvas is more reliable than a WebGL
    // context when the Gradio iframe or game screen is repeatedly hidden.
    type: Phaser.CANVAS,
    parent: mountId,
    width: WORLD_WIDTH,
    height: WORLD_HEIGHT,
    backgroundColor: "#75bd79",
    scene: WorldScene,
    pixelArt: true,
    // FIT preserves the internal coordinate system while the screen is hidden.
    // RESIZE can observe a 0x0 hidden parent and leave WebGL rendering black.
    scale: { mode: Phaser.Scale.FIT, autoCenter: Phaser.Scale.CENTER_BOTH },
  });

  function drawMap(scene) {
    if (player) savedPlayerPosition = { x: player.x, y: player.y };
    scene.children.removeAll();
    const width = scene.scale.width || WORLD_WIDTH;
    const height = scene.scale.height || WORLD_HEIGHT;
    scene.add.rectangle(width / 2, height / 2, width, height, 0x75bd79);
    drawGrass(scene, width, height);
    scene.add.rectangle(width / 2, height * .5, width, 104, 0xdab86c).setStrokeStyle(5, 0x263238);
    scene.add.rectangle(width / 2, height * .7, 104, height * .42, 0xdab86c).setStrokeStyle(5, 0x263238);

    const buildings = positions(width, height);
    drawBuilding(scene, buildings.school, 0xe7b34d, 0xc94f46, "SCHOOL", "school");
    drawBuilding(scene, buildings.home, 0xe9955d, 0x6b4d83, "HOME", "home");
    drawBuilding(scene, buildings.hq, 0x4f7f78, 0x273d52, "GRANDMA", "hq");
    drawTrees(scene, width, height);

    player = scene.add.container(
      savedPlayerPosition?.x ?? width / 2,
      savedPlayerPosition?.y ?? height * .5,
    );
    const appearance = getPlayerAppearance?.() || {};
    const shirt = APPEARANCE_COLORS.shirt[appearance.shirt_color] || APPEARANCE_COLORS.shirt.red;
    const pants = APPEARANCE_COLORS.pants[appearance.pants_color] || APPEARANCE_COLORS.pants.navy;
    const hair = APPEARANCE_COLORS.hair[appearance.hair_color] || APPEARANCE_COLORS.hair.dark_brown;
    const shadow = scene.add.ellipse(0, 23, 34, 11, 0x263238, .32);
    const backpack = scene.add.rectangle(13, -1, 15, 30, 0xd5a637).setStrokeStyle(3, 0x17202a);
    const backPocket = scene.add.rectangle(17, 4, 7, 12, 0xf0ca58).setStrokeStyle(2, 0x17202a);
    const leftLeg = scene.add.rectangle(-7, 17, 9, 20, pants).setStrokeStyle(3, 0x17202a);
    const rightLeg = scene.add.rectangle(7, 17, 9, 20, pants).setStrokeStyle(3, 0x17202a);
    const leftShoe = scene.add.rectangle(-8, 28, 13, 7, 0x202a35).setStrokeStyle(2, 0x17202a);
    const rightShoe = scene.add.rectangle(8, 28, 13, 7, 0x202a35).setStrokeStyle(2, 0x17202a);
    const leftArm = scene.add.rectangle(-16, 0, 8, 25, shirt).setStrokeStyle(3, 0x17202a).setAngle(8);
    const body = scene.add.rectangle(0, -1, 25, 31, shirt).setStrokeStyle(3, 0x17202a);
    const collar = scene.add.triangle(0, -11, -7, 0, 7, 0, 0, 7, 0xfff2c6).setStrokeStyle(2, 0x17202a);
    const rightArm = scene.add.rectangle(16, 0, 8, 25, shirt).setStrokeStyle(3, 0x17202a).setAngle(-8);
    const neck = scene.add.rectangle(0, -19, 8, 7, 0xe8ae7c).setStrokeStyle(2, 0x17202a);
    const head = scene.add.rectangle(0, -30, 23, 21, 0xf1bd8b).setStrokeStyle(3, 0x17202a);
    const hairBack = scene.add.rectangle(0, -36, 25, 11, hair).setStrokeStyle(3, 0x17202a);
    const hairFringe = scene.add.rectangle(-6, -31, 12, 7, hair);
    const eyeLeft = scene.add.rectangle(-5, -29, 2, 3, 0x17202a);
    const eyeRight = scene.add.rectangle(5, -29, 2, 3, 0x17202a);
    player.add([shadow, backpack, backPocket, leftLeg, rightLeg, leftShoe, rightShoe, leftArm, body, collar, rightArm, neck, head, hairBack, hairFringe, eyeLeft, eyeRight]);
    updateNearby();
  }

  function positions(width, height) {
    return {
      school: { x: width * .2, y: height * .28, width: 230, height: 145 },
      home: { x: width * .8, y: height * .28, width: 215, height: 140 },
      hq: { x: width * .5, y: height * .84, width: 270, height: 130 },
    };
  }

  function drawGrass(scene, width, height) {
    const graphics = scene.add.graphics();
    graphics.lineStyle(2, 0x5aaa69, .5);
    for (let x = 18; x < width; x += 38) {
      for (let y = 22; y < height; y += 36) graphics.lineBetween(x, y, x + 4, y - 8);
    }
  }

  function drawBuilding(scene, item, wall, roof, label, kind) {
    const { x, y, width, height } = item;
    scene.add.rectangle(x, y, width, height, wall).setStrokeStyle(6, 0x17202a);
    const roofShape = scene.add.triangle(x, y - height / 2 - 38, 0, 74, width / 2 + 22, 0, width + 44, 74, roof).setStrokeStyle(6, 0x17202a);
    roofShape.setOrigin(.5);
    scene.add.rectangle(x, y + height / 2 - 35, 50, 70, 0xfff2c6).setStrokeStyle(4, 0x17202a);
    scene.add.rectangle(x - width * .28, y - 8, 42, 38, 0x9fe1e0).setStrokeStyle(4, 0x17202a);
    scene.add.rectangle(x + width * .28, y - 8, 42, 38, 0x9fe1e0).setStrokeStyle(4, 0x17202a);
    const signWidth = Math.min(width - 24, Math.max(100, label.length * 14));
    scene.add.rectangle(x, y - 8, signWidth, 32, 0xfff2c6, .96).setStrokeStyle(3, 0x17202a);
    scene.add.text(x, y - 8, label, {
      fontFamily: "monospace", fontSize: "16px", fontStyle: "bold", color: "#17202a", align: "center",
      wordWrap: { width: width - 30 },
    }).setOrigin(.5);
    scene.add.zone(x, y, width, height + 70).setInteractive({ useHandCursor: true }).on("pointerdown", () => {
      if (active) onEnterBuilding(kind);
    });
  }

  function drawTrees(scene, width, height) {
    const locations = [[.06,.17],[.36,.17],[.64,.16],[.94,.18],[.08,.72],[.88,.72],[.23,.84],[.77,.86]];
    for (const [rx, ry] of locations) {
      const x = width * rx; const y = height * ry;
      scene.add.rectangle(x, y + 23, 14, 48, 0x80543d).setStrokeStyle(3, 0x17202a);
      scene.add.circle(x, y - 5, 34, 0x3f8b58).setStrokeStyle(4, 0x17202a);
      scene.add.circle(x - 22, y + 4, 23, 0x55a665).setStrokeStyle(3, 0x17202a);
      scene.add.circle(x + 22, y + 4, 23, 0x55a665).setStrokeStyle(3, 0x17202a);
    }
  }

  function move(dx, dy) {
    if (!sceneRef || !player) return;
    player.x = Phaser.Math.Clamp(player.x + dx, 28, sceneRef.scale.width - 28);
    player.y = Phaser.Math.Clamp(player.y + dy, 50, sceneRef.scale.height - 30);
    updateNearby();
  }

  function updateNearby() {
    if (!sceneRef || !player) return;
    const list = positions(sceneRef.scale.width, sceneRef.scale.height);
    nearbyBuilding = Object.entries(list).find(([, item]) =>
      Phaser.Math.Distance.Between(player.x, player.y, item.x, item.y + item.height / 2) < 125,
    )?.[0] || null;
    onNearbyChange(nearbyBuilding);
  }

  function enterNearby() {
    if (nearbyBuilding) onEnterBuilding(nearbyBuilding);
  }

  return {
    activate() {
      active = true;
      if (sceneRef) {
        sceneRef.scene.resume();
        // A hidden Canvas can be cleared by the browser. Wait until the world
        // screen has completed layout, then refresh and repaint the scene.
        requestAnimationFrame(() => requestAnimationFrame(() => {
          if (!active || !sceneRef) return;
          sceneRef.scale.refresh();
          drawMap(sceneRef);
          sceneRef.game.loop.wake();
        }));
      }
    },
    deactivate() {
      active = false;
      pressedKeys.clear();
      nearbyBuilding = null;
      if (sceneRef) {
        sceneRef.scene.pause();
      }
      onNearbyChange(null);
    },
    moveDirection(direction) {
      if (!active) return;
      const amount = 30;
      const vectors = { up: [0, -amount], down: [0, amount], left: [-amount, 0], right: [amount, 0] };
      const [dx, dy] = vectors[direction] || [0, 0];
      move(dx, dy);
    },
    enterNearby,
    getPlayerPosition() {
      if (player) return { x: player.x, y: player.y };
      return savedPlayerPosition;
    },
    redraw() { if (sceneRef) drawMap(sceneRef); },
    destroy() {
      window.removeEventListener("keydown", handleKeyDown);
      window.removeEventListener("keyup", handleKeyUp);
      game.destroy(true);
    },
  };
}
