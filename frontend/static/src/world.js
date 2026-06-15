import { createCharacter, preloadCharacter, updateCharacter } from "./character.js";

const WORLD_WIDTH = 960;
const WORLD_HEIGHT = 640;

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
  let playerRig = null;
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
      preloadCharacter(this, getPlayerAppearance?.() || {});
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
      updateCharacter(playerRig, dx, dy, this.time.now);
      if (dx || dy) move(dx, dy);
    }
  }

  const game = new Phaser.Game({
    // Canvas is more reliable than a WebGL context when the Gradio iframe or
    // game screen is repeatedly hidden.
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

    playerRig = createCharacter(
      scene,
      savedPlayerPosition?.x ?? width / 2,
      savedPlayerPosition?.y ?? height * .5,
      getPlayerAppearance?.() || {},
    );
    player = playerRig.container;
    updateCharacter(playerRig, 0, 0, 0);
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
