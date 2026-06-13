const API_BASE = "";
const WORLD_WIDTH = 760;
const WORLD_HEIGHT = 560;

const ui = {
  overlay: document.querySelector("#overlay"),
  panelTitle: document.querySelector("#panelTitle"),
  statusText: document.querySelector("#statusText"),
  authPanel: document.querySelector("#authPanel"),
  worldPanel: document.querySelector("#worldPanel"),
  schoolPanel: document.querySelector("#schoolPanel"),
  homePanel: document.querySelector("#homePanel"),
  hqPanel: document.querySelector("#hqPanel"),
  answerPanel: document.querySelector("#answerPanel"),
  registerTab: document.querySelector("#registerTab"),
  loginTab: document.querySelector("#loginTab"),
  authForm: document.querySelector("#authForm"),
  usernameInput: document.querySelector("#usernameInput"),
  passwordInput: document.querySelector("#passwordInput"),
  levelInput: document.querySelector("#levelInput"),
  levelLabel: document.querySelector("#levelLabel"),
  avatarLabel: document.querySelector("#avatarLabel"),
  avatarInput: document.querySelector("#avatarInput"),
  cameraTools: document.querySelector("#cameraTools"),
  startCameraButton: document.querySelector("#startCameraButton"),
  captureCameraButton: document.querySelector("#captureCameraButton"),
  cameraPreview: document.querySelector("#cameraPreview"),
  cameraCanvas: document.querySelector("#cameraCanvas"),
  authSubmitButton: document.querySelector("#authSubmitButton"),
  agentName: document.querySelector("#agentName"),
  agentLevel: document.querySelector("#agentLevel"),
  activeMission: document.querySelector("#activeMission"),
  interactButton: document.querySelector("#interactButton"),
  logoutButton: document.querySelector("#logoutButton"),
  lessonForm: document.querySelector("#lessonForm"),
  topicInput: document.querySelector("#topicInput"),
  lessonReader: document.querySelector("#lessonReader"),
  lessonStepTitle: document.querySelector("#lessonStepTitle"),
  lessonStepBody: document.querySelector("#lessonStepBody"),
  lessonStepExample: document.querySelector("#lessonStepExample"),
  prevStepButton: document.querySelector("#prevStepButton"),
  nextStepButton: document.querySelector("#nextStepButton"),
  teacherQuestionForm: document.querySelector("#teacherQuestionForm"),
  teacherQuestionInput: document.querySelector("#teacherQuestionInput"),
  teacherAnswer: document.querySelector("#teacherAnswer"),
  startQuizButton: document.querySelector("#startQuizButton"),
  phoneButton: document.querySelector("#phoneButton"),
  deskButton: document.querySelector("#deskButton"),
  bedButton: document.querySelector("#bedButton"),
  phoneDialog: document.querySelector("#phoneDialog"),
  practicePanel: document.querySelector("#practicePanel"),
  practiceSearchInput: document.querySelector("#practiceSearchInput"),
  practiceList: document.querySelector("#practiceList"),
  bossName: document.querySelector("#bossName"),
  bossBriefing: document.querySelector("#bossBriefing"),
  startBossButton: document.querySelector("#startBossButton"),
  questionModeLabel: document.querySelector("#questionModeLabel"),
  questionText: document.querySelector("#questionText"),
  battleStats: document.querySelector("#battleStats"),
  answerInput: document.querySelector("#answerInput"),
  answerCanvas: document.querySelector("#answerCanvas"),
  clearCanvasButton: document.querySelector("#clearCanvasButton"),
  submitAnswerButton: document.querySelector("#submitAnswerButton"),
  feedbackText: document.querySelector("#feedbackText"),
};

const state = {
  mode: "auth",
  authMode: "register",
  user: null,
  gameState: null,
  latestLesson: null,
  currentStepIndex: 0,
  currentQuestion: null,
  currentAnswerMode: "quiz",
  boss: null,
  nearbyBuilding: null,
  busy: false,
  avatarImageDataUrl: null,
};

// The Phaser scene only owns the game-like spaces: world movement and room art.
// DOM panels own forms and API controls because they are easier to iterate.
class SecretStudentScene extends Phaser.Scene {
  constructor() {
    super("SecretStudentScene");
    this.player = null;
    this.cursors = null;
    this.buildingLabels = [];
  }

  create() {
    this.cameras.main.setBackgroundColor("#7dcfb6");
    this.cursors = this.input.keyboard.createCursorKeys();
    this.wasd = this.input.keyboard.addKeys("W,A,S,D,SPACE,ENTER");
    this.drawWorld();
    this.input.keyboard.on("keydown-SPACE", () => interactWithNearby());
    this.input.keyboard.on("keydown-ENTER", () => interactWithNearby());
  }

  update() {
    if (!this.player || state.mode !== "world") return;
    const speed = 3.1;
    let dx = 0;
    let dy = 0;
    if (this.cursors.left.isDown || this.wasd.A.isDown) dx -= speed;
    if (this.cursors.right.isDown || this.wasd.D.isDown) dx += speed;
    if (this.cursors.up.isDown || this.wasd.W.isDown) dy -= speed;
    if (this.cursors.down.isDown || this.wasd.S.isDown) dy += speed;
    movePlayer(dx, dy);
  }

  drawWorld() {
    this.clearScene();
    state.mode = "world";
    this.add.rectangle(WORLD_WIDTH / 2, WORLD_HEIGHT / 2, WORLD_WIDTH, WORLD_HEIGHT, 0x7dcfb6);
    drawGrid(this, 40, 0x64b6ac);
    this.add.rectangle(380, 286, 650, 92, 0xe9c46a).setStrokeStyle(3, 0x18202f);
    this.add.text(280, 252, "Main Street", pixelText(22, "#18202f"));
    drawBuilding(this, 150, 150, 170, 120, 0x2a9d8f, "School", "school");
    drawBuilding(this, 610, 150, 170, 120, 0xf4a261, "Home", "home");
    const hqName = state.user ? `${state.user.username}'s Grandma's House` : "Grandma's House";
    drawBuilding(this, 380, 420, 230, 120, 0x264653, hqName, "hq");
    this.player = this.add.rectangle(380, 292, 26, 34, 0xd64045).setStrokeStyle(3, 0x18202f);
    this.add.rectangle(380, 282, 18, 14, 0xffd6a5).setStrokeStyle(2, 0x18202f);
    updateNearbyBuilding();
  }

  drawSchool() {
    this.clearScene();
    this.add.rectangle(WORLD_WIDTH / 2, WORLD_HEIGHT / 2, WORLD_WIDTH, WORLD_HEIGHT, 0xf4f1de);
    this.add.rectangle(380, 160, 560, 190, 0x153f33).setStrokeStyle(8, 0x6d4c41);
    this.add.text(170, 94, "Secret School", pixelText(30, "#fffdfa"));
    this.add.rectangle(200, 430, 260, 120, 0xfffdfa).setStrokeStyle(4, 0x18202f);
    this.add.text(110, 398, "Notebook", pixelText(22, "#18202f"));
    this.add.rectangle(610, 442, 90, 120, 0x9aa6b2).setStrokeStyle(3, 0x18202f);
    this.add.text(574, 385, "Door", pixelText(18, "#18202f"));
  }

  drawHome() {
    this.clearScene();
    this.add.rectangle(WORLD_WIDTH / 2, WORLD_HEIGHT / 2, WORLD_WIDTH, WORLD_HEIGHT, 0xf7e1d7);
    this.add.rectangle(160, 420, 220, 90, 0x8ecae6).setStrokeStyle(4, 0x18202f);
    this.add.text(102, 392, "Bed", pixelText(20, "#18202f"));
    this.add.rectangle(580, 390, 170, 100, 0xdda15e).setStrokeStyle(4, 0x18202f);
    this.add.text(520, 350, "Practice Desk", pixelText(18, "#18202f"));
    this.add.rectangle(365, 230, 66, 90, 0xd64045).setStrokeStyle(4, 0x18202f);
    this.add.text(275, 164, "Secret Phone", pixelText(24, "#18202f"));
    this.add.rectangle(380, 70, 140, 80, 0xbee3db).setStrokeStyle(4, 0x18202f);
  }

  drawHQ() {
    this.clearScene();
    this.add.rectangle(WORLD_WIDTH / 2, WORLD_HEIGHT / 2, WORLD_WIDTH, WORLD_HEIGHT, 0x22223b);
    this.add.rectangle(380, 150, 560, 150, 0x4a4e69).setStrokeStyle(4, 0xf3c969);
    this.add.text(162, 96, "Totally Normal Grandma Room", pixelText(24, "#fffdfa"));
    this.add.rectangle(380, 390, 420, 120, 0x9a8c98).setStrokeStyle(4, 0xf3c969);
    this.add.text(236, 352, "Mission Console", pixelText(24, "#fffdfa"));
  }

  drawBattle() {
    this.clearScene();
    this.add.rectangle(WORLD_WIDTH / 2, WORLD_HEIGHT / 2, WORLD_WIDTH, WORLD_HEIGHT, 0x1b263b);
    this.add.rectangle(540, 160, 170, 130, 0xd64045).setStrokeStyle(5, 0xfffdfa);
    this.add.text(470, 226, state.boss?.boss_name || "Boss", pixelText(20, "#fffdfa"));
    this.add.rectangle(170, 390, 90, 110, 0x2a9d8f).setStrokeStyle(5, 0xfffdfa);
    this.add.text(92, 456, "Secret Student", pixelText(18, "#fffdfa"));
  }

  clearScene() {
    this.children.removeAll();
    state.nearbyBuilding = null;
    this.player = null;
  }
}

const scene = new SecretStudentScene();
const game = new Phaser.Game({
  type: Phaser.AUTO,
  parent: "phaserMount",
  width: WORLD_WIDTH,
  height: WORLD_HEIGHT,
  backgroundColor: "#7dcfb6",
  scene,
  scale: { mode: Phaser.Scale.FIT, autoCenter: Phaser.Scale.CENTER_BOTH },
});

const notebook = createNotebook(ui.answerCanvas);

bootstrap();

ui.registerTab.addEventListener("click", () => setAuthMode("register"));
ui.loginTab.addEventListener("click", () => setAuthMode("login"));
ui.authForm.addEventListener("submit", submitAuth);
ui.avatarInput.addEventListener("change", readAvatarFile);
ui.startCameraButton.addEventListener("click", startCamera);
ui.captureCameraButton.addEventListener("click", captureCamera);
ui.logoutButton.addEventListener("click", logout);
ui.interactButton.addEventListener("click", interactWithNearby);
ui.lessonForm.addEventListener("submit", startLesson);
ui.prevStepButton.addEventListener("click", () => changeLessonStep(-1));
ui.nextStepButton.addEventListener("click", () => changeLessonStep(1));
ui.teacherQuestionForm.addEventListener("submit", askTeacher);
ui.startQuizButton.addEventListener("click", startQuiz);
ui.phoneButton.addEventListener("click", showMissionPhone);
ui.deskButton.addEventListener("click", showPractice);
ui.bedButton.addEventListener("click", restAtHome);
ui.practiceSearchInput.addEventListener("input", renderPracticeList);
ui.startBossButton.addEventListener("click", startBoss);
ui.submitAnswerButton.addEventListener("click", submitAnswer);
ui.clearCanvasButton.addEventListener("click", () => notebook.clear());
document.querySelectorAll("[data-move]").forEach((button) => {
  button.addEventListener("click", () => moveByButton(button.dataset.move));
});

async function bootstrap() {
  try {
    const me = await apiGet("/api/me");
    state.user = me.user;
    state.gameState = me.game_state;
    state.latestLesson = me.latest_lesson;
    hydrateAgentPanel();
    if (!state.gameState.onboarding_complete) {
      showOnboarding();
    } else {
      showWorld("Welcome back. Choose a building and press Enter.");
    }
  } catch {
    showAuth();
  }
}

function showAuth() {
  state.mode = "auth";
  setVisible("auth");
  ui.panelTitle.textContent = "Agent File";
  ui.statusText.textContent = "Register or log in to start the mission.";
  ui.overlay.textContent = "";
}

function showOnboarding() {
  setVisible("world");
  state.mode = "onboarding";
  ui.panelTitle.textContent = "Codename Grandma";
  ui.statusText.textContent = "Your first briefing is ready.";
  ui.overlay.textContent =
    "Grandma: School gives you the knowledge, home gives you missions, and my house is absolutely not secret headquarters.";
  setTimeout(async () => {
    await apiPost("/api/state/location", {
      location: "school",
      story_milestone: "onboarding_complete",
    });
    state.gameState.onboarding_complete = true;
    showWorld("First stop: enter School and pick something to learn.");
  }, 3200);
}

function showWorld(message = "") {
  setVisible("world");
  state.mode = "world";
  scene.drawWorld();
  ui.panelTitle.textContent = "World Map";
  ui.statusText.textContent = message || "Walk to a building and enter.";
  ui.overlay.textContent = "Arrow keys or WASD move. Space, Enter, or the Enter button opens a nearby building.";
  hydrateAgentPanel();
}

async function enterBuilding(kind) {
  await apiPost("/api/state/location", { location: kind });
  if (kind === "school") {
    setVisible("school");
    state.mode = "school";
    scene.drawSchool();
    ui.panelTitle.textContent = "School";
    ui.statusText.textContent = "Ask for a topic and the teacher will prepare a lesson.";
    ui.overlay.textContent = "The blackboard is ready. Your notebook waits for answers later.";
    renderLessonReader();
  }
  if (kind === "home") {
    setVisible("home");
    state.mode = "home";
    scene.drawHome();
    ui.panelTitle.textContent = "Home";
    ui.statusText.textContent = "Check your phone or practice at the desk.";
    ui.overlay.textContent = "Home base: missions arrive by phone, practice happens at the desk.";
  }
  if (kind === "hq") {
    setVisible("hq");
    state.mode = "hq";
    scene.drawHQ();
    ui.panelTitle.textContent = "Grandma's House";
    ui.statusText.textContent = "No one suspects a thing.";
    hydrateBossPanel();
    ui.overlay.textContent = "The mission console hums quietly behind a very normal lamp.";
  }
}

async function submitAuth(event) {
  event.preventDefault();
  const payload = {
    username: ui.usernameInput.value.trim(),
    password: ui.passwordInput.value,
  };
  if (state.authMode === "register") {
    payload.learner_level = ui.levelInput.value;
    payload.avatar_image_data_url = state.avatarImageDataUrl;
  }
  setBusy(true, state.authMode === "register" ? "Creating your agent file..." : "Checking credentials...");
  try {
    const response = await apiPost(`/api/auth/${state.authMode}`, payload);
    state.user = response.user;
    state.gameState = response.game_state;
    state.latestLesson = null;
    hydrateAgentPanel();
    if (state.gameState.onboarding_complete) showWorld();
    else showOnboarding();
  } catch (error) {
    showError(error);
  } finally {
    setBusy(false);
  }
}

async function logout() {
  await apiPost("/api/auth/logout", {});
  state.user = null;
  state.gameState = null;
  state.latestLesson = null;
  showAuth();
}

async function startLesson(event) {
  event.preventDefault();
  setBusy(true, "The teacher is preparing your secret lesson...");
  ui.overlay.textContent = "Teacher: While I set up the blackboard, organize your notes like a careful agent.";
  try {
    const lesson = await apiPost("/api/lesson/start", { topic: ui.topicInput.value.trim() });
    state.latestLesson = lesson;
    state.currentStepIndex = 0;
    renderLessonReader();
    hydrateAgentPanel();
    ui.statusText.textContent = "Lesson ready. Read each step, then try the mini quiz.";
  } catch (error) {
    showError(error);
  } finally {
    setBusy(false);
  }
}

function renderLessonReader() {
  const hasLesson = Boolean(state.latestLesson);
  ui.lessonReader.hidden = !hasLesson;
  if (!hasLesson) return;
  const steps = state.latestLesson.lesson_steps;
  const step = steps[state.currentStepIndex];
  ui.lessonStepTitle.textContent = step.title;
  ui.lessonStepBody.textContent = step.body;
  ui.lessonStepExample.textContent = step.example || "";
  ui.prevStepButton.disabled = state.currentStepIndex === 0;
  ui.nextStepButton.disabled = state.currentStepIndex >= steps.length - 1;
  ui.startQuizButton.disabled = state.currentStepIndex < steps.length - 1;
}

function changeLessonStep(delta) {
  if (!state.latestLesson) return;
  const max = state.latestLesson.lesson_steps.length - 1;
  state.currentStepIndex = Math.max(0, Math.min(max, state.currentStepIndex + delta));
  renderLessonReader();
}

async function askTeacher(event) {
  event.preventDefault();
  if (!state.latestLesson || !ui.teacherQuestionInput.value.trim()) return;
  setBusy(true, "Asking the teacher...");
  try {
    const response = await apiPost(`/api/lesson/${state.latestLesson.id}/ask`, {
      step_index: state.currentStepIndex,
      question: ui.teacherQuestionInput.value.trim(),
    });
    ui.teacherAnswer.textContent = response.answer;
    ui.teacherQuestionInput.value = "";
  } catch (error) {
    showError(error);
  } finally {
    setBusy(false);
  }
}

function startQuiz() {
  if (!state.latestLesson?.quiz_questions.length) return;
  state.currentAnswerMode = "quiz";
  state.currentQuestion = state.latestLesson.quiz_questions[0];
  showAnswerPanel("Mini Quiz", "Answer the question. Type if you can, or draw in the notebook.");
}

async function startBoss() {
  if (!state.latestLesson) return;
  setBusy(true, "Opening the hidden mission console...");
  try {
    const response = await apiPost("/api/boss/start", { lesson_id: state.latestLesson.id });
    state.boss = response;
    state.currentAnswerMode = "boss";
    state.currentQuestion = response.question;
    scene.drawBattle();
    showAnswerPanel("Boss Battle", response.briefing);
    renderBattleStats();
  } catch (error) {
    showError(error);
  } finally {
    setBusy(false);
  }
}

function showAnswerPanel(label, message) {
  setVisible("answer");
  notebook.clear();
  ui.feedbackText.textContent = "";
  ui.answerInput.value = "";
  ui.panelTitle.textContent = label;
  ui.questionModeLabel.textContent = label;
  ui.statusText.textContent = message;
  ui.overlay.textContent = message;
  ui.questionText.textContent = state.currentQuestion.question;
  ui.answerInput.focus();
}

async function submitAnswer() {
  if (!state.latestLesson || !state.currentQuestion) return;
  const answerText = ui.answerInput.value.trim();
  const payload = {
    lesson_id: state.latestLesson.id,
    question_id: state.currentQuestion.id,
    mode: state.currentAnswerMode,
    answer_text: answerText || null,
    image_data_url: answerText ? null : notebook.toDataUrlIfUsed(),
  };
  if (!payload.answer_text && !payload.image_data_url) {
    ui.feedbackText.textContent = "Type an answer or write one in the notebook.";
    return;
  }
  setBusy(true, "Checking your answer...");
  try {
    const endpoint = state.currentAnswerMode === "boss" ? "/api/boss/submit" : "/api/quiz/submit";
    const response = await apiPost(endpoint, payload);
    ui.feedbackText.textContent = response.result.feedback;
    if (state.currentAnswerMode === "boss") {
      handleBossResponse(response);
    } else {
      handleQuizResponse(response);
    }
  } catch (error) {
    showError(error);
  } finally {
    setBusy(false);
  }
}

function handleQuizResponse(response) {
  if (response.completed) {
    ui.statusText.textContent = "Quiz complete. Go home and wait for the secret phone.";
    ui.overlay.textContent = "Teacher: Good work. Head home when you are ready.";
    setTimeout(() => showWorld("Go home for your mission call."), 1600);
    return;
  }
  state.currentQuestion = response.next_question;
  ui.questionText.textContent = state.currentQuestion.question;
  ui.answerInput.value = "";
  notebook.clear();
}

function handleBossResponse(response) {
  state.boss = response;
  renderBattleStats();
  if (response.defeated) {
    ui.statusText.textContent = "Boss defeated. The world is safer because you studied.";
    ui.overlay.textContent = `${response.boss_name} retreats. Mission complete.`;
    setTimeout(() => showWorld("Mission complete. Pick a new lesson when ready."), 2200);
    return;
  }
  if (response.lost) {
    ui.statusText.textContent = "Mission failed for now. Rest at home, then try again.";
    ui.overlay.textContent = "Grandma: Tactical retreat. Home, rest, return.";
    setTimeout(() => showWorld("Go home to rest before retrying the boss."), 2200);
    return;
  }
  state.currentQuestion = response.question;
  ui.questionText.textContent = state.currentQuestion.question;
  ui.answerInput.value = "";
  notebook.clear();
}

function renderBattleStats() {
  if (!state.boss) {
    ui.battleStats.textContent = "";
    return;
  }
  ui.battleStats.textContent =
    `Question ${state.boss.question_index}/${state.boss.total_questions}. ` +
    `Mistakes remaining: ${state.boss.mistakes_remaining}.`;
}

function showMissionPhone() {
  ui.practicePanel.hidden = true;
  ui.phoneDialog.hidden = false;
  if (!state.latestLesson) {
    ui.phoneDialog.textContent =
      "Secret phone: No active mission yet. Go to school and learn a topic first.";
    return;
  }
  const boss = state.latestLesson.boss_mission;
  ui.phoneDialog.textContent =
    `Secret phone: We need to defeat ${boss.boss_name}. ` +
    `Review ${state.latestLesson.topic}, then visit Grandma's house when ready.`;
}

function showPractice() {
  ui.phoneDialog.hidden = true;
  ui.practicePanel.hidden = false;
  renderPracticeList();
}

function renderPracticeList() {
  ui.practiceList.innerHTML = "";
  if (!state.latestLesson) {
    ui.practiceList.textContent = "No notes yet. Go to school first.";
    return;
  }
  const search = ui.practiceSearchInput.value.trim().toLowerCase();
  const items = [
    ...state.latestLesson.lesson_steps.map((step) => ({
      title: step.title,
      body: `${step.body} ${step.example || ""}`,
    })),
    ...state.latestLesson.quiz_questions.map((question) => ({
      title: question.question,
      body: question.explanation || question.expected_answer,
    })),
  ].filter((item) => `${item.title} ${item.body}`.toLowerCase().includes(search));
  for (const item of items) {
    const node = document.createElement("article");
    node.className = "practice-item";
    node.innerHTML = `<strong></strong><p></p>`;
    node.querySelector("strong").textContent = item.title;
    node.querySelector("p").textContent = item.body;
    ui.practiceList.append(node);
  }
}

async function restAtHome() {
  await apiPost("/api/state/location", { location: "home", story_milestone: "rest" });
  ui.statusText.textContent = "You rested. Health restored for another try.";
  ui.overlay.textContent = "A good night's sleep restores agent focus.";
}

function hydrateBossPanel() {
  if (!state.latestLesson) {
    ui.bossName.textContent = "No boss yet";
    ui.bossBriefing.textContent = "Finish a lesson first, then come here for the mission.";
    ui.startBossButton.disabled = true;
    return;
  }
  ui.bossName.textContent = state.latestLesson.boss_mission.boss_name;
  ui.bossBriefing.textContent = state.latestLesson.boss_mission.briefing;
  ui.startBossButton.disabled = false;
}

function hydrateAgentPanel() {
  ui.agentName.textContent = state.user?.username || "-";
  ui.agentLevel.textContent = state.user?.learner_level || "-";
  ui.activeMission.textContent = state.latestLesson?.topic || state.gameState?.active_topic || "None yet";
}

function interactWithNearby() {
  if (state.mode !== "world") {
    showWorld("Back on the map.");
    return;
  }
  if (state.nearbyBuilding) enterBuilding(state.nearbyBuilding);
}

function moveByButton(direction) {
  if (state.mode !== "world") return;
  const amount = 24;
  const vectors = {
    up: [0, -amount],
    down: [0, amount],
    left: [-amount, 0],
    right: [amount, 0],
  };
  const [dx, dy] = vectors[direction] || [0, 0];
  movePlayer(dx, dy);
}

function movePlayer(dx, dy) {
  if (!scene.player) return;
  scene.player.x = Phaser.Math.Clamp(scene.player.x + dx, 24, WORLD_WIDTH - 24);
  scene.player.y = Phaser.Math.Clamp(scene.player.y + dy, 24, WORLD_HEIGHT - 24);
  updateNearbyBuilding();
}

function updateNearbyBuilding() {
  if (!scene.player) return;
  const buildings = [
    { kind: "school", x: 150, y: 150 },
    { kind: "home", x: 610, y: 150 },
    { kind: "hq", x: 380, y: 420 },
  ];
  const nearby = buildings.find((building) =>
    Phaser.Math.Distance.Between(scene.player.x, scene.player.y, building.x, building.y) < 110
  );
  state.nearbyBuilding = nearby?.kind || null;
  ui.interactButton.disabled = !state.nearbyBuilding;
  if (state.mode === "world") {
    ui.statusText.textContent = state.nearbyBuilding
      ? `Near ${labelForBuilding(state.nearbyBuilding)}. Press Enter.`
      : "Walk to a building and enter.";
  }
}

function labelForBuilding(kind) {
  if (kind === "school") return "School";
  if (kind === "home") return "Home";
  return "Grandma's House";
}

function drawBuilding(sceneRef, x, y, width, height, color, label, kind) {
  sceneRef.add.rectangle(x, y, width, height, color).setStrokeStyle(4, 0x18202f);
  sceneRef.add.rectangle(x, y + height / 2 - 18, 46, 36, 0xfffdfa).setStrokeStyle(3, 0x18202f);
  sceneRef.add.text(x - width / 2 + 12, y - 18, label, pixelText(18, "#fffdfa"));
  sceneRef.add.text(x - 28, y + height / 2 + 26, "Enter", pixelText(14, "#18202f"));
  const zone = sceneRef.add.zone(x, y, width, height).setInteractive({ useHandCursor: true });
  zone.on("pointerdown", () => enterBuilding(kind));
}

function drawGrid(sceneRef, size, color) {
  const graphics = sceneRef.add.graphics();
  graphics.lineStyle(1, color, 0.45);
  for (let x = 0; x <= WORLD_WIDTH; x += size) graphics.lineBetween(x, 0, x, WORLD_HEIGHT);
  for (let y = 0; y <= WORLD_HEIGHT; y += size) graphics.lineBetween(0, y, WORLD_WIDTH, y);
}

function pixelText(size, color) {
  return {
    fontFamily: "monospace",
    fontSize: `${size}px`,
    color,
    fontStyle: "bold",
    wordWrap: { width: 260 },
  };
}

function setAuthMode(mode) {
  state.authMode = mode;
  ui.registerTab.classList.toggle("active", mode === "register");
  ui.loginTab.classList.toggle("active", mode === "login");
  ui.levelLabel.hidden = mode !== "register";
  ui.avatarLabel.hidden = mode !== "register";
  ui.cameraTools.hidden = mode !== "register";
  ui.authSubmitButton.textContent = mode === "register" ? "Create Agent File" : "Login";
}

async function readAvatarFile() {
  const file = ui.avatarInput.files?.[0];
  if (!file) return;
  state.avatarImageDataUrl = await fileToDataUrl(file);
}

async function startCamera() {
  if (!navigator.mediaDevices?.getUserMedia) {
    ui.statusText.textContent = "Webcam is not available in this browser.";
    return;
  }
  const stream = await navigator.mediaDevices.getUserMedia({ video: true, audio: false });
  ui.cameraPreview.srcObject = stream;
  ui.cameraPreview.hidden = false;
  ui.captureCameraButton.hidden = false;
  await ui.cameraPreview.play();
}

function captureCamera() {
  const context = ui.cameraCanvas.getContext("2d");
  context.drawImage(ui.cameraPreview, 0, 0, ui.cameraCanvas.width, ui.cameraCanvas.height);
  state.avatarImageDataUrl = ui.cameraCanvas.toDataURL("image/png");
  ui.cameraCanvas.hidden = false;
}

function fileToDataUrl(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(reader.result);
    reader.onerror = reject;
    reader.readAsDataURL(file);
  });
}

function setVisible(section) {
  const map = {
    auth: ui.authPanel,
    world: ui.worldPanel,
    school: ui.schoolPanel,
    home: ui.homePanel,
    hq: ui.hqPanel,
    answer: ui.answerPanel,
  };
  Object.values(map).forEach((panel) => {
    panel.hidden = true;
  });
  map[section].hidden = false;
}

function setBusy(isBusy, message = "") {
  state.busy = isBusy;
  if (message) ui.statusText.textContent = message;
  document.querySelectorAll("button, input, select").forEach((element) => {
    if (element.id === "logoutButton") return;
    element.disabled = isBusy;
  });
  if (!isBusy) {
    ui.interactButton.disabled = state.mode === "world" && !state.nearbyBuilding;
    if (state.latestLesson) renderLessonReader();
    hydrateBossPanel();
  }
}

async function apiGet(path) {
  const response = await fetch(`${API_BASE}${path}`, { credentials: "include" });
  return parseResponse(response);
}

async function apiPost(path, payload) {
  const response = await fetch(`${API_BASE}${path}`, {
    method: "POST",
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return parseResponse(response);
}

async function parseResponse(response) {
  const contentType = response.headers.get("content-type") || "";
  const body = contentType.includes("application/json") ? await response.json() : await response.text();
  if (!response.ok) {
    const message = typeof body === "object" ? body.detail || JSON.stringify(body) : body;
    throw new Error(message || `HTTP ${response.status}`);
  }
  return body;
}

function showError(error) {
  ui.statusText.textContent = error.message || "Something went wrong.";
  ui.overlay.textContent = ui.statusText.textContent;
}

function createNotebook(canvas) {
  const context = canvas.getContext("2d");
  let drawing = false;
  let used = false;
  let last = null;

  function clear() {
    used = false;
    context.fillStyle = "#fbfaf4";
    context.fillRect(0, 0, canvas.width, canvas.height);
    context.strokeStyle = "#d8d4c8";
    context.lineWidth = 1;
    for (let y = 36; y < canvas.height; y += 36) {
      context.beginPath();
      context.moveTo(0, y);
      context.lineTo(canvas.width, y);
      context.stroke();
    }
    context.strokeStyle = "#2a9d8f";
    context.lineWidth = 5;
    context.strokeRect(4, 4, canvas.width - 8, canvas.height - 8);
  }

  function point(event) {
    const rect = canvas.getBoundingClientRect();
    return {
      x: ((event.clientX - rect.left) / rect.width) * canvas.width,
      y: ((event.clientY - rect.top) / rect.height) * canvas.height,
    };
  }

  function start(event) {
    drawing = true;
    used = true;
    last = point(event);
    event.preventDefault();
  }

  function move(event) {
    if (!drawing || !last) return;
    const next = point(event);
    context.strokeStyle = "#18202f";
    context.lineWidth = 12;
    context.lineCap = "round";
    context.lineJoin = "round";
    context.beginPath();
    context.moveTo(last.x, last.y);
    context.lineTo(next.x, next.y);
    context.stroke();
    last = next;
    event.preventDefault();
  }

  function stop() {
    drawing = false;
    last = null;
  }

  canvas.addEventListener("pointerdown", start);
  canvas.addEventListener("pointermove", move);
  canvas.addEventListener("pointerup", stop);
  canvas.addEventListener("pointerleave", stop);
  clear();

  return {
    clear,
    toDataUrlIfUsed: () => (used ? canvas.toDataURL("image/png") : null),
  };
}
