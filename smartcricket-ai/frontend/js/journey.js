// The next step uses saved evidence, never a guessed technique score.
(function (root) {
  function hasMeasurements(analysis) {
    const summary = analysis.summary || {};
    if (analysis.mode === "video") return Number(summary.tracked_frames) > 0;
    return Boolean(summary.detected) && Object.values(analysis.angles || {})
      .some(value => Number.isFinite(value?.deg));
  }

  function nextStep(history, status) {
    const latest = history.find(hasMeasurements);
    const today = status?.today;
    if (today?.rest_day) return {
      key: "recovery", title: "Make recovery today's focus",
      text: "Your check-in calls for rest. Open your recovery plan and leave batting drills for another day.",
      href: "training.html", label: "Open recovery plan", icon: "body",
    };
    if (!latest) return {
      key: "capture", title: history.length ? "Start with a clearer capture" : "Build your first batting baseline",
      text: history.length
        ? "Your saved captures do not yet contain usable joint measurements. Keep the full batter in frame, use good light, and try a side-on photo."
        : "Upload one clear, side-on batting photo. Your posture report will explain the measured angles and help personalise your practice.",
      href: "image.html", label: history.length ? "Retake a photo" : "Analyse my first photo", icon: "camera",
    };
    if (!today) return {
      key: "unavailable", title: "Your latest report is ready",
      text: "Training status could not be loaded. You can still review your saved measurements or retry the dashboard.",
      href: `${latest.mode === "video" ? "clip" : "analysis"}.html?id=${latest.id}`,
      label: "Open latest report", icon: "doc",
    };
    if (!today.checked_in) return {
      key: "checkin", title: "Turn your analysis into today's plan",
      text: "Complete a short check-in about yesterday's practice, soreness, and energy so your daily plan suits how you feel.",
      href: "training.html", label: "Check in with my coach", icon: "chat",
    };
    if (!today.drills_total || today.drills_done < today.drills_total) return {
      key: "practice", title: today.drills_total ? "Continue today's practice" : "Prepare today's practice",
      text: today.drills_total
        ? `${today.drills_done} of ${today.drills_total} drills complete. Open your plan for instructions or use the live mirror for supported drills.`
        : "Your check-in is saved. Open Training to prepare your personalised drill plan.",
      href: "training.html", label: "Open my training plan", icon: "dumbbell",
    };
    if (!today.quiz_done) return {
      key: "quiz", title: "Finish with a quick knowledge check",
      text: "Today's drills are complete. Answer the daily question to reinforce what you learned.",
      href: "training.html", label: "Answer today's question", icon: "quiz",
    };
    return {
      key: "progress", title: "Today's plan is complete",
      text: "Your check-in, drills, and daily question are saved. Review your consistency and weekly summary, then return for your next session.",
      href: "progress.html", label: "Review my progress", icon: "chart",
    };
  }

  root.SmartCricketJourney = { hasMeasurements, nextStep };
  if (typeof module !== "undefined" && module.exports) module.exports = root.SmartCricketJourney;
})(globalThis);
