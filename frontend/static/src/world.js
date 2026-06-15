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
  const heldDirections = new Set();

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
  function clearMovement() {
    pressedKeys.clear();
    heldDirections.clear();
  }

  window.addEventListener("blur", clearMovement);

  class WorldScene extends Phaser.Scene {
    constructor() { super("WorldScene"); }

    preload() {
      this.load.image("world-map-agent", "/game-static/assets/world-map-agent.png");
    }

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
      if (pressedKeys.has("arrowleft") || pressedKeys.has("a") || heldDirections.has("left")) dx -= speed;
      if (pressedKeys.has("arrowright") || pressedKeys.has("d") || heldDirections.has("right")) dx += speed;
      if (pressedKeys.has("arrowup") || pressedKeys.has("w") || heldDirections.has("up")) dy -= speed;
      if (pressedKeys.has("arrowdown") || pressedKeys.has("s") || heldDirections.has("down")) dy += speed;
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
    scene.add.image(width / 2, height / 2, "world-map-agent").setDisplaySize(width, height);

    const buildings = positions(width, height);
    drawBuildingHotspot(scene, buildings.school, "SCHOOL", "school");
    drawBuildingHotspot(scene, buildings.home, "HOME", "home");
    drawBuildingHotspot(scene, buildings.hq, "GRANDMA", "hq");

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
      school: { x: width * .24, y: height * .23, width: width * .36, height: height * .35, entranceX: width * .25, entranceY: height * .4 },
      home: { x: width * .74, y: height * .23, width: width * .25, height: height * .34, entranceX: width * .75, entranceY: height * .4 },
      hq: { x: width * .5, y: height * .79, width: width * .25, height: height * .28, entranceX: width * .52, entranceY: height * .91 },
    };
  }

  function drawBuildingHotspot(scene, item, label, kind) {
    const { x, y, width, height, entranceX, entranceY } = item;
    scene.add.text(entranceX, entranceY - 20, label, {
      fontFamily: "monospace", fontSize: "13px", fontStyle: "bold", color: "#17202a",
      backgroundColor: "#fff2c7", padding: { x: 7, y: 4 },
    }).setOrigin(.5).setStroke("#fff2c7", 2);
    scene.add.zone(x, y, width, height + 70).setInteractive({ useHandCursor: true }).on("pointerdown", () => {
      if (active) onEnterBuilding(kind);
    });
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
      Phaser.Math.Distance.Between(player.x, player.y, item.entranceX, item.entranceY) < 105,
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
      heldDirections.clear();
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
    startMoving(direction) {
      if (!active || !["up", "down", "left", "right"].includes(direction)) return;
      heldDirections.add(direction);
      this.moveDirection(direction);
    },
    stopMoving(direction) {
      heldDirections.delete(direction);
    },
    stopAllMovement() {
      heldDirections.clear();
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
      window.removeEventListener("blur", clearMovement);
      game.destroy(true);
    },
  };
}
