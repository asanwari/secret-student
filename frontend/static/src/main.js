import { getJson, postJson } from "./api.js";
import { createNotebook } from "./notebook.js";
import { createScreenRouter } from "./router.js";
import { createWorldController } from "./world.js";

const $ = (selector) => document.querySelector(selector);
const $$ = (selector) => [...document.querySelectorAll(selector)];

const ui = {
  registerTab: $("#registerTab"), loginTab: $("#loginTab"), authForm: $("#authForm"),
  username: $("#usernameInput"), password: $("#passwordInput"), level: $("#levelInput"),
  levelLabel: $("#levelLabel"), avatarLabel: $("#avatarLabel"), avatar: $("#avatarInput"),
  cameraTools: $("#cameraTools"), cameraPreview: $("#cameraPreview"), cameraCanvas: $("#cameraCanvas"),
  startCamera: $("#startCameraButton"), captureCamera: $("#captureCameraButton"),
  authSubmit: $("#authSubmitButton"), authStatus: $("#authStatus"), loading: $("#loadingCurtain"), loadingText: $("#loadingText"),
  onboardingText: $("#onboardingText"), continueOnboarding: $("#continueOnboardingButton"),
  agentName: $("#agentName"), activeMission: $("#activeMission"), logout: $("#logoutButton"),
  worldPrompt: $("#worldPrompt"), interact: $("#interactButton"),
  lessonForm: $("#lessonForm"), topic: $("#topicInput"), lessonReader: $("#lessonReader"),
  lessonProgress: $("#lessonProgress"), lessonTitle: $("#lessonStepTitle"), lessonBody: $("#lessonStepBody"),
  lessonExample: $("#lessonStepExample"), previousStep: $("#prevStepButton"), nextStep: $("#nextStepButton"),
  teacherForm: $("#teacherQuestionForm"), teacherQuestion: $("#teacherQuestionInput"),
  teacherChat: $("#teacherChat"), teacherChatMessages: $("#teacherChatMessages"),
  closeTeacherChat: $("#closeTeacherChat"), teacherFollowupForm: $("#teacherFollowupForm"),
  teacherFollowup: $("#teacherFollowupInput"),
  newTopic: $("#newTopicButton"), startQuiz: $("#startQuizButton"), schoolStatus: $("#schoolStatus"),
  phone: $("#phoneButton"), desk: $("#deskButton"), bed: $("#bedButton"), homeDialog: $("#homeDialog"),
  closeHomeDialog: $("#closeHomeDialog"), phoneDialog: $("#phoneDialog"), practicePanel: $("#practicePanel"),
  practiceSearch: $("#practiceSearchInput"), practiceList: $("#practiceList"), homeStatus: $("#homeStatus"),
  bossName: $("#bossName"), bossBriefing: $("#bossBriefing"), startBoss: $("#startBossButton"),
  quizQuestion: $("#quizQuestionText"), quizAnswer: $("#quizAnswerInput"), quizFeedback: $("#quizFeedback"),
  clearQuiz: $("#clearQuizCanvasButton"), submitQuiz: $("#submitQuizAnswerButton"),
  battleBossName: $("#battleBossName"), battleStats: $("#battleStats"), bossQuestion: $("#bossQuestionText"),
  bossAnswer: $("#bossAnswerInput"), bossFeedback: $("#bossFeedback"), clearBoss: $("#clearBossCanvasButton"), submitBoss: $("#submitBossAnswerButton"),
};

const state = {
  authMode: "register", user: null, gameState: null, lesson: null, lessonStep: 0,
  nearbyBuilding: null, quizQuestion: null, bossQuestion: null, bossState: null,
  avatarDataUrl: null, onboardingIndex: 0,
  worldPosition: null,
  teacherChatKey: null, teacherChatHistory: [],
};

const quizNotebook = createNotebook($("#quizCanvas"));
const bossNotebook = createNotebook($("#bossCanvas"));

let world = null;

function ensureWorld() {
  if (world) return world;
  world = createWorldController({
    mountId: "worldMount",
    getPlayerName: () => state.user?.username || "AGENT",
    onNearbyChange: (building) => {
      state.nearbyBuilding = building;
      ui.interact.disabled = !building;
      ui.worldPrompt.textContent = building ? `Press Enter to visit ${buildingLabel(building)}.` : "Use WASD or arrow keys to explore.";
    },
    onEnterBuilding: enterBuilding,
    initialPlayerPosition: state.worldPosition,
  });
  return world;
}

const router = createScreenRouter({
  onBeforeChange(current) {
    if (current !== "world" || !world) return;
    state.worldPosition = world.getPlayerPosition();
    world.destroy();
    world = null;
    $("#worldMount").replaceChildren();
  },
  onAfterChange(next) {
    if (next === "world") {
      // Create Phaser only after the map element is visible and has dimensions.
      requestAnimationFrame(() => ensureWorld().activate());
    }
  },
});

wireEvents();
bootstrap();

async function bootstrap() {
  setLoading(true, "Opening classified records...");
  try {
    const me = await getJson("/api/me");
    state.user = me.user;
    state.gameState = me.game_state;
    state.lesson = me.latest_lesson;
    hydratePersistentUi();
    if (state.gameState.onboarding_complete) router.show("world", { replace: true });
    else startOnboarding(true);
  } catch {
    router.show("auth", { replace: true });
  } finally {
    setLoading(false);
  }
}

function wireEvents() {
  ui.registerTab.addEventListener("click", () => setAuthMode("register"));
  ui.loginTab.addEventListener("click", () => setAuthMode("login"));
  ui.authForm.addEventListener("submit", submitAuth);
  ui.avatar.addEventListener("change", readAvatar);
  ui.startCamera.addEventListener("click", startCamera);
  ui.captureCamera.addEventListener("click", captureCamera);
  ui.continueOnboarding.addEventListener("click", advanceOnboarding);
  ui.logout.addEventListener("click", logout);
  ui.interact.addEventListener("click", () => world?.enterNearby());
  $$('[data-move]').forEach((button) => button.addEventListener("click", () => world?.moveDirection(button.dataset.move)));
  $$('[data-back-to-world]').forEach((button) => button.addEventListener("click", () => goWorld("Back on the map.")));
  $$('[data-answer-exit]').forEach((button) => button.addEventListener("click", () => goWorld("You left the challenge.")));
  ui.lessonForm.addEventListener("submit", startLesson);
  ui.previousStep.addEventListener("click", () => changeLessonStep(-1));
  ui.nextStep.addEventListener("click", advanceLesson);
  ui.teacherForm.addEventListener("submit", askTeacher);
  ui.teacherFollowupForm.addEventListener("submit", askTeacherFollowup);
  ui.closeTeacherChat.addEventListener("click", () => { ui.teacherChat.hidden = true; });
  ui.newTopic.addEventListener("click", chooseNewTopic);
  ui.startQuiz.addEventListener("click", beginQuiz);
  ui.phone.addEventListener("click", showPhone);
  ui.desk.addEventListener("click", showPractice);
  ui.bed.addEventListener("click", rest);
  ui.closeHomeDialog.addEventListener("click", () => { ui.homeDialog.hidden = true; });
  ui.practiceSearch.addEventListener("input", renderPractice);
  ui.startBoss.addEventListener("click", beginBoss);
  ui.clearQuiz.addEventListener("click", quizNotebook.clear);
  ui.clearBoss.addEventListener("click", bossNotebook.clear);
  ui.submitQuiz.addEventListener("click", submitQuizAnswer);
  ui.submitBoss.addEventListener("click", submitBossAnswer);
  ui.quizAnswer.addEventListener("keydown", submitOnEnter(submitQuizAnswer));
  ui.bossAnswer.addEventListener("keydown", submitOnEnter(submitBossAnswer));
}

function submitOnEnter(callback) {
  return (event) => {
    if (event.key === "Enter") {
      event.preventDefault();
      callback();
    }
  };
}

function setAuthMode(mode) {
  state.authMode = mode;
  ui.registerTab.classList.toggle("active", mode === "register");
  ui.loginTab.classList.toggle("active", mode === "login");
  ui.levelLabel.hidden = mode !== "register";
  ui.avatarLabel.hidden = mode !== "register";
  ui.cameraTools.hidden = mode !== "register";
  ui.authSubmit.textContent = mode === "register" ? "Create Agent File" : "Enter Headquarters";
  ui.authStatus.textContent = "";
}

async function submitAuth(event) {
  event.preventDefault();
  const payload = { username: ui.username.value.trim(), password: ui.password.value };
  if (state.authMode === "register") {
    payload.learner_level = ui.level.value;
    payload.avatar_image_data_url = state.avatarDataUrl;
  }
  setLoading(true, state.authMode === "register" ? "Creating your cover identity..." : "Checking credentials...");
  try {
    const response = await postJson(`/api/auth/${state.authMode}`, payload);
    state.user = response.user;
    state.gameState = response.game_state;
    state.lesson = null;
    hydratePersistentUi();
    if (state.gameState.onboarding_complete) router.show("world");
    else startOnboarding();
  } catch (error) {
    ui.authStatus.textContent = error.message;
  } finally {
    setLoading(false);
  }
}

async function logout() {
  await postJson("/api/auth/logout");
  state.user = null; state.gameState = null; state.lesson = null;
  setAuthMode("login");
  router.show("auth");
}

const onboardingLines = [
  "Welcome, agent. To everyone else, you are an ordinary student.",
  "At School, choose a topic and learn the skills hidden inside it.",
  "At Home, your secret phone delivers missions and your desk stores practice notes.",
  "When you are ready, visit Grandma's House. Nobody suspects it is headquarters.",
];

function startOnboarding(replace = false) {
  state.onboardingIndex = 0;
  ui.onboardingText.textContent = onboardingLines[0];
  ui.continueOnboarding.textContent = "Continue";
  router.show("onboarding", { replace });
}

async function advanceOnboarding() {
  state.onboardingIndex += 1;
  if (state.onboardingIndex < onboardingLines.length) {
    ui.onboardingText.textContent = onboardingLines[state.onboardingIndex];
    ui.continueOnboarding.textContent = state.onboardingIndex === onboardingLines.length - 1 ? "Begin Mission" : "Continue";
    return;
  }
  await postJson("/api/state/location", { location: "world", story_milestone: "onboarding_complete" });
  state.gameState.onboarding_complete = true;
  goWorld("First stop: School.");
}

async function enterBuilding(kind) {
  if (!state.user || router.current() !== "world") return;
  await postJson("/api/state/location", { location: kind });
  if (kind === "school") {
    prepareSchool();
    router.show("school");
  } else if (kind === "home") {
    prepareHome();
    router.show("home");
  } else {
    prepareHq();
    router.show("hq");
  }
}

function goWorld(message) {
  hydratePersistentUi();
  router.show("world");
  ui.worldPrompt.textContent = message || "Use WASD or arrow keys to explore.";
}

function prepareSchool() {
  ui.schoolStatus.textContent = state.lesson ? `Current subject: ${state.lesson.topic}` : "The teacher is ready.";
  if (state.lesson) renderLesson();
  else {
    ui.lessonForm.hidden = false;
    ui.lessonReader.hidden = true;
  }
}

function chooseNewTopic() {
  ui.lessonReader.hidden = true;
  ui.lessonForm.hidden = false;
  ui.topic.value = "";
  ui.topic.focus();
  ui.schoolStatus.textContent = "Choose the next subject to investigate.";
}

async function startLesson(event) {
  event.preventDefault();
  setLoading(true, "The teacher is preparing the blackboard...");
  try {
    state.lesson = await postJson("/api/lesson/start", { topic: ui.topic.value.trim() });
    state.lessonStep = 0;
    resetTeacherChat();
    renderLesson();
    hydratePersistentUi();
    ui.schoolStatus.textContent = "Lesson ready.";
  } catch (error) {
    ui.schoolStatus.textContent = error.message;
  } finally {
    setLoading(false);
  }
}

function renderLesson() {
  if (!state.lesson) return;
  const steps = state.lesson.lesson_steps;
  const step = steps[state.lessonStep];
  ui.lessonForm.hidden = true;
  ui.lessonReader.hidden = false;
  ui.lessonProgress.textContent = `Lesson ${state.lessonStep + 1}/${steps.length}`;
  ui.lessonTitle.textContent = step.title;
  ui.lessonBody.textContent = step.body;
  ui.lessonExample.textContent = step.example || "";
  ui.previousStep.disabled = state.lessonStep === 0;
  const finalStep = state.lessonStep === steps.length - 1;
  ui.nextStep.disabled = false;
  ui.nextStep.textContent = finalStep ? "Start Quiz" : "Next";
  ui.startQuiz.hidden = !finalStep;
  ui.startQuiz.disabled = !finalStep;
  ui.schoolStatus.textContent = finalStep
    ? "Lesson complete. Select Start Quiz to open your notebook."
    : `Lesson step ${state.lessonStep + 1} of ${steps.length}.`;
}

function changeLessonStep(change) {
  if (!state.lesson) return;
  state.lessonStep = Math.max(0, Math.min(state.lesson.lesson_steps.length - 1, state.lessonStep + change));
  ensureTeacherChatForStep();
  renderLesson();
}

function advanceLesson() {
  if (!state.lesson) return;
  const finalStep = state.lessonStep === state.lesson.lesson_steps.length - 1;
  if (finalStep) beginQuiz();
  else changeLessonStep(1);
}

async function askTeacher(event) {
  event.preventDefault();
  const question = ui.teacherQuestion.value.trim();
  if (!question) return;
  ui.teacherQuestion.value = "";
  await sendTeacherQuestion(question);
}

async function askTeacherFollowup(event) {
  event.preventDefault();
  const question = ui.teacherFollowup.value.trim();
  if (!question) return;
  ui.teacherFollowup.value = "";
  await sendTeacherQuestion(question);
}

async function sendTeacherQuestion(question) {
  if (!state.lesson) return;
  ensureTeacherChatForStep();
  const priorHistory = state.teacherChatHistory.slice(-12);
  state.teacherChatHistory.push({ role: "student", content: question });
  renderTeacherChat();
  ui.teacherChat.hidden = false;
  setLoading(true, "The teacher is thinking...");
  try {
    const response = await postJson(`/api/lesson/${state.lesson.id}/ask`, {
      step_index: state.lessonStep,
      question,
      history: priorHistory,
    });
    state.teacherChatHistory.push({ role: "teacher", content: response.answer });
  } catch (error) {
    state.teacherChatHistory.push({ role: "teacher", content: `I could not answer that yet: ${error.message}` });
  } finally {
    setLoading(false);
    renderTeacherChat();
    ui.teacherFollowup.focus();
  }
}

function ensureTeacherChatForStep() {
  const key = state.lesson ? `${state.lesson.id}:${state.lessonStep}` : null;
  if (key === state.teacherChatKey) return;
  state.teacherChatKey = key;
  state.teacherChatHistory = [];
  ui.teacherChat.hidden = true;
  renderTeacherChat();
}

function resetTeacherChat() {
  state.teacherChatKey = null;
  state.teacherChatHistory = [];
  ensureTeacherChatForStep();
}

function renderTeacherChat() {
  ui.teacherChatMessages.replaceChildren();
  for (const message of state.teacherChatHistory) {
    const bubble = document.createElement("p");
    bubble.className = `chat-message ${message.role}`;
    bubble.textContent = message.content;
    ui.teacherChatMessages.append(bubble);
  }
  ui.teacherChatMessages.scrollTop = ui.teacherChatMessages.scrollHeight;
}

function beginQuiz() {
  if (!state.lesson?.quiz_questions.length) return;
  state.quizQuestion = state.lesson.quiz_questions[0];
  renderQuizQuestion();
  router.show("quiz");
  setTimeout(() => ui.quizAnswer.focus(), 0);
}

function renderQuizQuestion() {
  ui.quizQuestion.textContent = state.quizQuestion.question;
  ui.quizAnswer.value = "";
  ui.quizFeedback.textContent = "";
  quizNotebook.clear();
}

async function submitQuizAnswer() {
  const payload = answerPayload("quiz", state.quizQuestion, ui.quizAnswer, quizNotebook);
  if (!payload) { ui.quizFeedback.textContent = "Type or draw an answer first."; return; }
  setLoading(true, "Checking your notebook...");
  try {
    const response = await postJson("/api/quiz/submit", payload);
    ui.quizFeedback.textContent = response.result.feedback;
    if (response.completed) {
      ui.quizFeedback.textContent += " Quiz complete. Go home for your mission call.";
      setTimeout(() => goWorld("Head home for your mission briefing."), 1500);
    } else {
      state.quizQuestion = response.next_question;
      setTimeout(renderQuizQuestion, 700);
    }
  } catch (error) { ui.quizFeedback.textContent = error.message; }
  finally { setLoading(false); }
}

function prepareHome() {
  ui.homeDialog.hidden = true;
  ui.homeStatus.textContent = state.lesson ? "Your secret phone is flashing." : "Visit School to begin a mission.";
}

function showPhone() {
  ui.homeDialog.hidden = false;
  ui.phoneDialog.hidden = false;
  ui.practicePanel.hidden = true;
  ui.phoneDialog.textContent = state.lesson
    ? `Agent, ${state.lesson.boss_mission.boss_name} is attacking everything connected to ${state.lesson.topic}. Practice if needed, then report to Grandma's House.`
    : "No mission yet. Your next assignment begins at School.";
}

function showPractice() {
  ui.homeDialog.hidden = false;
  ui.phoneDialog.hidden = true;
  ui.practicePanel.hidden = false;
  renderPractice();
}

function renderPractice() {
  ui.practiceList.replaceChildren();
  if (!state.lesson) { ui.practiceList.textContent = "No notes yet."; return; }
  const query = ui.practiceSearch.value.trim().toLowerCase();
  const notes = [
    ...state.lesson.lesson_steps.map((step) => ({ title: step.title, body: `${step.body} ${step.example || ""}` })),
    ...state.lesson.quiz_questions.map((question) => ({ title: question.question, body: question.explanation })),
  ].filter((note) => `${note.title} ${note.body}`.toLowerCase().includes(query));
  for (const note of notes) {
    const article = document.createElement("article");
    article.className = "practice-item";
    const title = document.createElement("strong"); title.textContent = note.title;
    const body = document.createElement("p"); body.textContent = note.body;
    article.append(title, body); ui.practiceList.append(article);
  }
}

async function rest() {
  await postJson("/api/state/location", { location: "home", story_milestone: "rest" });
  ui.homeStatus.textContent = "You rested. Agent health restored.";
}

function prepareHq() {
  ui.bossName.textContent = state.lesson?.boss_mission.boss_name || "No boss detected";
  ui.bossBriefing.textContent = state.lesson?.boss_mission.briefing || "Complete a lesson before opening the vault.";
  ui.startBoss.disabled = !state.lesson;
}

async function beginBoss() {
  if (!state.lesson) return;
  setLoading(true, "Unlocking the mission vault...");
  try {
    state.bossState = await postJson("/api/boss/start", { lesson_id: state.lesson.id });
    state.bossQuestion = state.bossState.question;
    renderBossQuestion();
    router.show("boss");
    setTimeout(() => ui.bossAnswer.focus(), 0);
  } catch (error) { ui.bossBriefing.textContent = error.message; }
  finally { setLoading(false); }
}

function renderBossQuestion() {
  ui.battleBossName.textContent = state.bossState.boss_name;
  ui.battleStats.textContent = `Question ${state.bossState.question_index}/${state.bossState.total_questions} | Mistakes left: ${state.bossState.mistakes_remaining}`;
  ui.bossQuestion.textContent = state.bossQuestion.question;
  ui.bossAnswer.value = "";
  ui.bossFeedback.textContent = "";
  bossNotebook.clear();
}

async function submitBossAnswer() {
  const payload = answerPayload("boss", state.bossQuestion, ui.bossAnswer, bossNotebook);
  if (!payload) { ui.bossFeedback.textContent = "Transmit an answer first."; return; }
  setLoading(true, "Resolving attack...");
  try {
    const response = await postJson("/api/boss/submit", payload);
    ui.bossFeedback.textContent = response.result.feedback;
    state.bossState = response;
    if (response.defeated) {
      ui.bossFeedback.textContent += " Mission complete. The world is safe.";
      setTimeout(() => goWorld("Mission complete. School is ready for a new topic."), 1800);
    } else if (response.lost) {
      ui.bossFeedback.textContent += " Retreat home and rest before trying again.";
      setTimeout(() => goWorld("Return home to recover."), 1800);
    } else {
      state.bossQuestion = response.question;
      setTimeout(renderBossQuestion, 700);
    }
  } catch (error) { ui.bossFeedback.textContent = error.message; }
  finally { setLoading(false); }
}

function answerPayload(mode, question, input, notebook) {
  if (!state.lesson || !question) return null;
  const text = input.value.trim();
  const image = text ? null : notebook.toDataUrlIfUsed();
  if (!text && !image) return null;
  return { lesson_id: state.lesson.id, question_id: question.id, mode, answer_text: text || null, image_data_url: image };
}

function hydratePersistentUi() {
  ui.agentName.textContent = state.user?.username || "-";
  ui.activeMission.textContent = state.lesson?.topic || state.gameState?.active_topic || "Find a lesson";
}

function buildingLabel(kind) {
  if (kind === "school") return "School";
  if (kind === "home") return "Home";
  return `${state.user?.username || "Agent"}'s Grandma's House`;
}

async function readAvatar() {
  const file = ui.avatar.files?.[0];
  if (!file) return;
  state.avatarDataUrl = await fileToDataUrl(file);
}

async function startCamera() {
  if (!navigator.mediaDevices?.getUserMedia) { ui.authStatus.textContent = "Webcam is unavailable."; return; }
  const stream = await navigator.mediaDevices.getUserMedia({ video: true, audio: false });
  ui.cameraPreview.srcObject = stream;
  ui.cameraPreview.hidden = false;
  ui.captureCamera.hidden = false;
  await ui.cameraPreview.play();
}

function captureCamera() {
  const context = ui.cameraCanvas.getContext("2d");
  context.drawImage(ui.cameraPreview, 0, 0, ui.cameraCanvas.width, ui.cameraCanvas.height);
  state.avatarDataUrl = ui.cameraCanvas.toDataURL("image/png");
  ui.cameraCanvas.hidden = false;
}

function fileToDataUrl(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader(); reader.onload = () => resolve(reader.result); reader.onerror = reject; reader.readAsDataURL(file);
  });
}

function setLoading(visible, text = "Loading...") {
  ui.loading.hidden = !visible;
  ui.loadingText.textContent = text;
}
