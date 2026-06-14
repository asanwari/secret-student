from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
INDEX = (ROOT / "frontend/static/index.html").read_text()
MAIN_JS = (ROOT / "frontend/static/src/main.js").read_text()
API_JS = (ROOT / "frontend/static/src/api.js").read_text()
WORLD_JS = (ROOT / "frontend/static/src/world.js").read_text()
STYLES = (ROOT / "frontend/static/src/styles.css").read_text()


def test_auth_is_the_only_initially_visible_game_screen():
    assert 'data-screen="auth"' in INDEX
    for screen in ("onboarding", "world", "school", "home", "hq", "quiz", "boss"):
        assert f'data-screen="{screen}" hidden' in INDEX


def test_space_auth_uses_bearer_token_when_iframe_cookies_are_blocked():
    assert "sessionStorage.setItem" in API_JS
    assert "headers.Authorization = `Bearer ${token}`" in API_JS
    assert "setSessionToken(response.session_token)" in MAIN_JS
    assert "setSessionToken(null)" in MAIN_JS


def test_world_is_created_lazily_after_authentication():
    assert "let world = null" in MAIN_JS
    assert "function ensureWorld()" in MAIN_JS
    assert 'if (next === "world")' in MAIN_JS


def test_world_keyboard_is_disabled_off_screen_and_ignores_editable_focus():
    assert 'if (!active || isEditableTarget(event.target)' in WORLD_JS
    assert 'window.addEventListener("keydown", handleKeyDown)' in WORLD_JS
    assert "pressedKeys.clear()" in WORLD_JS
    assert "isEditableTarget(document.activeElement)" in WORLD_JS
    assert 'target.matches("input, textarea, select' in WORLD_JS


def test_world_uses_fixed_internal_resolution_to_avoid_hidden_canvas_collapse():
    assert "Phaser.Scale.FIT" in WORLD_JS
    assert "mode: Phaser.Scale.RESIZE" not in WORLD_JS
    assert "type: Phaser.CANVAS" in WORLD_JS


def test_world_does_not_use_phaser_global_keyboard_capture():
    assert "createCursorKeys" not in WORLD_JS
    assert "addKeys" not in WORLD_JS


def test_world_repaints_after_becoming_visible_again():
    assert "getPlayerPosition()" in WORLD_JS
    assert "initialPlayerPosition" in WORLD_JS
    assert "world.destroy()" in MAIN_JS
    assert "world = null" in MAIN_JS
    assert '$("#worldMount").replaceChildren()' in MAIN_JS


def test_final_lesson_step_leads_directly_to_quiz():
    assert 'ui.nextStep.textContent = finalStep ? "Start Quiz" : "Next"' in MAIN_JS
    assert "function advanceLesson()" in MAIN_JS
    assert "if (finalStep) beginQuiz()" in MAIN_JS


def test_teacher_chat_supports_close_scroll_and_chained_questions():
    assert '$("#closeTeacherChat")' in MAIN_JS
    assert 'ui.teacherChat.hidden = true' in MAIN_JS
    assert "teacherChatHistory" in MAIN_JS
    assert "history: priorHistory" in MAIN_JS
    assert "scrollTop = ui.teacherChatMessages.scrollHeight" in MAIN_JS
    assert "scrollElementToTop(ui.teacherChatMessages, latestTeacher)" in MAIN_JS
    assert 'querySelector(".chat-message.teacher:last-of-type")' in MAIN_JS


def test_lesson_navigation_scrolls_reader_to_top_with_reduced_motion_support():
    assert "scrollToStart(ui.lessonReader)" in MAIN_JS
    assert 'window.matchMedia?.("(prefers-reduced-motion: reduce)")' in MAIN_JS
    assert 'top: 0, behavior: prefersReducedMotion() ? "auto" : "smooth"' in MAIN_JS


def test_character_customization_is_registered_and_used_by_world():
    assert 'id="appearanceFields"' in INDEX
    assert 'name="shirtColor"' in INDEX
    assert 'name="pantsColor"' in INDEX
    assert 'name="hairColor"' in INDEX
    assert "payload.character_appearance = selectedAppearance()" in MAIN_JS
    assert "getPlayerAppearance" in WORLD_JS
    assert "APPEARANCE_COLORS" in WORLD_JS
    assert "backpack" in WORLD_JS


def test_quiz_and_boss_wait_for_explicit_progression():
    assert 'id="nextQuizQuestionButton"' in INDEX
    assert 'id="nextBossQuestionButton"' in INDEX
    assert 'id="quizProgressBar"' in INDEX
    assert 'id="bossProgressBar"' in INDEX
    assert "advanceQuizAfterFeedback" in MAIN_JS
    assert "advanceBossAfterFeedback" in MAIN_JS
    assert "setTimeout(renderQuizQuestion" not in MAIN_JS
    assert "setTimeout(renderBossQuestion" not in MAIN_JS


def test_quiz_and_boss_use_forms_and_typed_answers_take_precedence():
    assert 'id="quizAnswerForm"' in INDEX
    assert 'id="bossAnswerForm"' in INDEX
    assert 'id="submitQuizAnswerButton" type="submit"' in INDEX
    assert 'id="submitBossAnswerButton" type="submit"' in INDEX
    assert 'ui.quizForm.addEventListener("submit", submitQuizAnswer)' in MAIN_JS
    assert 'ui.bossForm.addEventListener("submit", submitBossAnswer)' in MAIN_JS
    assert "const image = text ? null : notebook.toDataUrlIfUsed()" in MAIN_JS
    assert "event?.preventDefault()" in MAIN_JS


def test_answer_feedback_has_visual_states_and_resets():
    assert 'setFeedback("quiz", response.result.correct ? "correct" : "incorrect"' in MAIN_JS
    assert 'setFeedback("boss", response.result.correct ? "correct" : "incorrect"' in MAIN_JS
    assert 'setFeedback("quiz", "neutral", "")' in MAIN_JS
    assert 'setFeedback("boss", "neutral", "")' in MAIN_JS
    assert '.feedback-line[data-status="correct"]' in STYLES
    assert '.feedback-line[data-status="incorrect"]' in STYLES
    assert '.battle-console[data-feedback="correct"]' in STYLES
    assert '.notebook-page[data-feedback="incorrect"]' in STYLES


def test_touch_navigation_supports_press_and_hold_cleanup():
    assert "const heldDirections = new Set()" in WORLD_JS
    assert "startMoving(direction)" in WORLD_JS
    assert "stopMoving(direction)" in WORLD_JS
    assert "heldDirections.clear()" in WORLD_JS
    assert 'window.addEventListener("blur", clearMovement)' in WORLD_JS
    assert 'window.removeEventListener("blur", clearMovement)' in WORLD_JS
    assert 'button.addEventListener("pointerdown"' in MAIN_JS
    assert 'button.addEventListener("pointerup", stop)' in MAIN_JS
    assert 'button.addEventListener("pointercancel", stop)' in MAIN_JS
    assert 'button.addEventListener("lostpointercapture"' in MAIN_JS
    assert "touch-action: none" in STYLES


def test_generated_room_and_character_art_are_wired_with_fallbacks():
    assert "/game-static/assets/bedroom-agent.png" in (ROOT / "frontend/static/src/styles.css").read_text()
    assert "/game-static/assets/codename-grandma.png" in INDEX
    assert "/game-static/assets/villain-default.png" in INDEX
    assert "safeVillainUrl" in MAIN_JS
    assert 'drawBuilding(scene, buildings.hq, 0x4f7f78, 0x273d52, "GRANDMA"' in WORLD_JS
