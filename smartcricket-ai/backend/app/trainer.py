"""Adaptive virtual coaching (module M9): levels, XP, streaks, daily drill plans, check-ins, quiz and weekly reports.

Everything here is computed from the player's own stored data with fixed rules, so it works without the AI model.
The language model is only used to word the weekly summary and to answer free chat, and its replies go through
the same "no invented numbers" check as the analysis coach.
"""
import json
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from . import coach
from .config import settings
from .models import (Analysis, DailyLog, LiveSession, Media, PlanDrill, QuizAnswer, Reflection, TrainingChat,
                     User, WeeklyReport)


def today() -> date:
    return datetime.now().astimezone().date()


def local_day(dt: datetime) -> date:
    return dt.astimezone().date()


def monday(d: date) -> date:
    return d - timedelta(days=d.weekday())


# ---------------------------------------------------------------- drill library

# code: (title, how to do it, unit, base sets, base reps)
DRILLS = {
    "knee_bend": ("Front-knee bend shadow drill",
                  "From a side-on stance, stride forward into a shadow drive and hold the front knee bent over the toes "
                  "for two seconds before returning.", "reps", 3, 10),
    "hip_hinge": ("Hip-hinge stance hold",
                  "Take your stance, push the hips back a little with a straight back and hold, weight on the balls "
                  "of the feet.", "s hold", 3, 20),
    "level_shoulders": ("Level-shoulders mirror drill",
                        "Shadow-bat facing a mirror or your phone camera. Keep the head still and the eyes level from "
                        "backlift to finish.", "reps", 3, 8),
    "high_backlift": ("Backlift hold",
                      "Lift the bat to the top of your backlift, hold for three seconds with the front shoulder "
                      "pointing down the pitch, then play a slow shadow shot.", "reps", 3, 8),
    "elbow_lead": ("Front-elbow lead drill",
                   "Play slow shadow drives letting the front elbow lead the bat to the ball and finish with the "
                   "elbow high.", "reps", 3, 10),
    "film_setup": ("Camera set-up photo",
                   "Take one side-on photo at hip height with your whole body and bat in the frame, then analyse it "
                   "in the app.", "photo", 1, 1),
    "shot_shadow": ("Shadow practice: {shot}",
                    "Play the {shot} slowly without a ball, pausing at the backlift, contact point and finish.",
                    "reps", 3, 10),
    # general drills, used to fill the plan
    "shadow_batting": ("Shadow batting round",
                       "Play each of your main shots slowly without a ball and check your balance at the finish.",
                       "reps", 3, 12),
    "footwork": ("Forward-and-back footwork",
                 "Mark a crease line. Alternate one big stride forward and one step back and across, returning to "
                 "your stance each time.", "reps", 3, 10),
    "balance_hold": ("Finish-position balance",
                     "Play a shadow drive and hold the finish on the front foot for three seconds without wobbling.",
                     "reps", 3, 8),
    "drop_ball": ("Drop-ball defence",
                  "A partner drops a ball from shoulder height in front of you. Play a soft forward defence with the "
                  "bat face angled down.", "reps", 3, 10),
    "ball_watch": ("Ball-watching call",
                   "A partner shows 1 to 5 fingers on the ball hand as they throw. Call the number before you play "
                   "your shadow shot.", "reps", 3, 10),
    "rest": ("Rest and light mobility",
             "No batting today. Ten minutes of easy walking and gentle stretching only. If the soreness continues, "
             "talk to a doctor or physiotherapist.", "min", 1, 10),
}
GENERAL = ["shadow_batting", "footwork", "balance_hold", "drop_ball", "ball_watch"]
DIFFICULTY = {1: "Easy", 2: "Normal", 3: "Hard"}


def dose(code: str, difficulty: int) -> tuple[str, int, int]:
    _, _, unit, sets, reps = DRILLS[code]
    if unit == "photo":
        return "1 photo", 1, 1
    if unit == "min":
        return f"{reps} min", 1, reps
    sets = max(1, sets + difficulty - 2)
    reps = max(1, round(reps * {1: .7, 2: 1, 3: 1.3}[difficulty]))
    return (f"{sets} × {reps} s hold" if unit == "s hold" else f"{sets} × {reps} reps"), sets, reps


# ---------------------------------------------------------------- the player's data

@dataclass
class Ctx:
    user: User
    day: date
    analyses: list = field(default_factory=list)   # oldest first
    logs: dict = field(default_factory=dict)        # day -> DailyLog
    drills: list = field(default_factory=list)
    quiz: dict = field(default_factory=dict)        # day -> QuizAnswer
    reflected: set = field(default_factory=set)     # analysis ids
    live: list = field(default_factory=list)        # saved live-mirror sessions


def load(user: User, db: Session) -> Ctx:
    c = Ctx(user=user, day=today())
    c.analyses = db.scalars(select(Analysis).join(Media).where(Media.user_id == user.id)
                            .order_by(Analysis.created_at)).all()
    c.logs = {l.day: l for l in db.scalars(select(DailyLog).where(DailyLog.user_id == user.id))}
    c.drills = db.scalars(select(PlanDrill).where(PlanDrill.user_id == user.id).order_by(PlanDrill.id)).all()
    c.quiz = {q.day: q for q in db.scalars(select(QuizAnswer).where(QuizAnswer.user_id == user.id))}
    c.reflected = set(db.scalars(select(Reflection.analysis_id).where(Reflection.user_id == user.id)))
    c.live = db.scalars(select(LiveSession).where(LiveSession.user_id == user.id).order_by(LiveSession.id)).all()
    return c


def photos(c: Ctx) -> list:
    return [a for a in c.analyses if a.mode == "image" and (a.summary or {}).get("detected")]


def deg(a, joint):
    return ((a.angles or {}).get(joint) or {}).get("deg")


def bent(a, joint):
    """The more bent (smaller) of the two sides, e.g. the front knee in a drive."""
    vals = [v for v in (deg(a, f"left_{joint}"), deg(a, f"right_{joint}")) if v is not None]
    return min(vals) if vals else None


def mean(xs):
    xs = [x for x in xs if x is not None]
    return round(sum(xs) / len(xs), 1) if xs else None


# ---------------------------------------------------------------- streaks, XP and levels

def active_days(c: Ctx) -> Counter:
    """A practice day is any day with an analysis, a finished drill or a check-in."""
    days = Counter(local_day(a.created_at) for a in c.analyses)
    days.update(d.day for d in c.drills if d.done)
    days.update(c.logs.keys())
    days.update(s.day for s in c.live)
    return days


def streaks(days, day: date) -> tuple[int, int]:
    cur, d = 0, day if day in days else day - timedelta(days=1)  # a streak survives until the end of today
    while d in days:
        cur, d = cur + 1, d - timedelta(days=1)
    best = run = 0
    prev = None
    for d in sorted(days):
        run = run + 1 if prev and d - prev == timedelta(days=1) else 1
        best, prev = max(best, run), d
    return cur, best


def full_photos(c: Ctx) -> int:
    return sum(1 for a in photos(c) if a.angles and all(v.get("deg") is not None for v in a.angles.values()))


def complete_days(c: Ctx) -> set:
    by_day = defaultdict(list)
    for d in c.drills:
        by_day[d.day].append(d.done)
    return {d for d, done in by_day.items() if all(done)}


def plan_weeks(c: Ctx) -> int:
    """Weeks (Monday to Sunday) with every drill finished on at least 5 days."""
    weeks = Counter(monday(d) for d in complete_days(c))
    return sum(1 for n in weeks.values() if n >= 5)


XP_RULES = {"analysis": 10, "drill": 15, "checkin": 5, "quiz_right": 10, "quiz_wrong": 3, "active_day": 5, "streak_day": 5,
            "live": 5}


def xp(c: Ctx, days) -> dict:
    right = sum(1 for q in c.quiz.values() if q.correct)
    parts = {
        "analysis": len(c.analyses) * XP_RULES["analysis"],
        "drill": sum(1 for d in c.drills if d.done) * XP_RULES["drill"],
        "checkin": len(c.logs) * XP_RULES["checkin"],
        "live": len(c.live) * XP_RULES["live"],
        "quiz": right * XP_RULES["quiz_right"] + (len(c.quiz) - right) * XP_RULES["quiz_wrong"],
        "streak": len(days) * XP_RULES["active_day"]
                  + sum(1 for d in days if d - timedelta(days=1) in days) * XP_RULES["streak_day"],
    }
    return {"total": sum(parts.values()), "parts": parts}


LEVELS = [
    (1, "Net Rookie", []),
    (2, "Club Batter", [("analyses", 5), ("best_streak", 3)]),
    (3, "District", [("analyses", 20), ("full_photos", 5)]),
    (4, "State", [("analyses", 40), ("plan_weeks", 2)]),
    (5, "Pro", [("analyses", 75), ("best_streak", 21)]),
]
REQ_LABELS = {"analyses": "analyses", "best_streak": "day streak (best ever)",
              "full_photos": "photos with all 8 joints measured", "plan_weeks": "weekly plans completed"}


def level_info(have: dict) -> dict:
    level = 1
    for n, _, reqs in LEVELS[1:]:
        if all(have[k] >= need for k, need in reqs):
            level = n
        else:
            break
    levels = [{"level": n, "name": name, "reached": n <= level,
               "requirements": [{"key": k, "label": REQ_LABELS[k], "have": have[k], "need": need,
                                 "done": have[k] >= need} for k, need in reqs]} for n, name, reqs in LEVELS]
    nxt = levels[level] if level < len(LEVELS) else None
    progress = 1.0 if nxt is None else sum(min(1, r["have"] / r["need"]) for r in nxt["requirements"]) / len(nxt["requirements"])
    return {"level": level, "name": LEVELS[level - 1][1], "next": nxt, "progress": round(progress, 3), "levels": levels}


def status(c: Ctx) -> dict:
    days = active_days(c)
    cur, best = streaks(days, c.day)
    have = {"analyses": len(c.analyses), "best_streak": best, "full_photos": full_photos(c), "plan_weeks": plan_weeks(c)}
    lv = level_info(have)
    todays = [d for d in c.drills if d.day == c.day]
    since = c.day - timedelta(days=69)
    return {
        "level": lv["level"], "level_name": lv["name"], "next": lv["next"], "progress": lv["progress"],
        "levels": lv["levels"], "xp": xp(c, days), "streak": cur, "best_streak": best,
        "today": {"checked_in": c.day in c.logs, "drills_done": sum(d.done for d in todays), "drills_total": len(todays),
                  "quiz_done": c.day in c.quiz},
        "days": {d.isoformat(): n for d, n in sorted(days.items()) if d >= since},
    }


# ---------------------------------------------------------------- weak spots and the daily plan

def measurements(a) -> dict | None:
    """The values the drill rules look at, from one photo or one clip (None if nothing usable was measured).
    A photo is one moment, so its more-bent side is used. A clip covers the whole stroke, so its deepest bend
    (smallest angle) and highest arm position (largest shoulder angle) are used."""
    s = a.summary or {}
    if a.mode == "image":
        if not s.get("detected"):
            return None
        return {"knee": bent(a, "knee"), "hip": bent(a, "hip"), "elbow": bent(a, "elbow"),
                "shoulder": mean([deg(a, "left_shoulder"), deg(a, "right_shoulder")]),
                "tilt": s.get("shoulder_line_deg"), "visible": s.get("visible")}
    r = s.get("joint_ranges") or {}
    if (s.get("tracked_frames") or 0) < 5 or not r:
        return None
    low = lambda j: min((r[k]["min"] for k in (f"left_{j}", f"right_{j}") if k in r), default=None)
    high = max((r[k]["max"] for k in ("left_shoulder", "right_shoulder") if k in r), default=None)
    # elbows fold right up at the top of every backlift, so take them at the frame of most movement (the swing)
    at_key = (s.get("angles_seq") or [{}])[s.get("key_frame") or 0]
    elbows = [v for v in (at_key.get("left_elbow"), at_key.get("right_elbow")) if v is not None]
    return {"knee": low("knee"), "hip": low("hip"), "elbow": min(elbows) if elbows else None, "shoulder": high,
            "tilt": None, "visible": None}


def weak_spots(c: Ctx) -> list[tuple[str, str, dict]]:
    """Drills chosen from the player's last five measured photos and clips. Thresholds are coaching rules of
    thumb on 2D estimates, used to pick practice, never to call technique right or wrong."""
    recent = [(a, m) for a in c.analyses if (m := measurements(a))][-5:]
    out = []
    if recent:
        def src(key):
            """'your last 2 photos and 3 clips', counting only the uploads that measured this value"""
            used = [a for a, m in recent if m[key] is not None]
            n_ph = sum(1 for a in used if a.mode == "image")
            parts = [f"{n} {w}{'s' if n > 1 else ''}" for n, w in ((n_ph, "photo"), (len(used) - n_ph, "clip")) if n]
            return "your last " + " and ".join(parts)
        avg = lambda k: mean(m[k] for _, m in recent)
        knee, hip, elbow, shoulder, tilt, visible = (avg(k) for k in ("knee", "hip", "elbow", "shoulder", "tilt", "visible"))
        if knee is not None and knee > 160:
            out.append(("knee_bend", f"Your knee bend averaged {knee}° across {src('knee')}, so this drill practises a deeper bend.", {"knee_avg_deg": knee}))
        if tilt is not None and tilt > 20:
            out.append(("level_shoulders", f"Your shoulder line tilted {tilt}° on average across {src('tilt')}.", {"shoulder_tilt_avg_deg": tilt}))
        if hip is not None and hip > 165:
            out.append(("hip_hinge", f"Your hips stayed fairly upright ({hip}° on average) across {src('hip')}.", {"hip_avg_deg": hip}))
        if elbow is not None and elbow < 80:
            out.append(("elbow_lead", f"Your more-bent elbow averaged {elbow}° across {src('elbow')}.", {"elbow_avg_deg": elbow}))
        if shoulder is not None and shoulder < 35:
            out.append(("high_backlift", f"Your arms stayed low (shoulder angle {shoulder}° on average) across {src('shoulder')}.", {"shoulder_avg_deg": shoulder}))
        if visible is not None and visible < 26:
            out.append(("film_setup", f"Only {visible} of 33 body points were visible on average, so a clearer photo will give better advice.", {"visible_avg": visible}))
    clips = [a for a in c.analyses if a.mode == "video" and a.shot and a.confidence is not None][-5:]
    unsure = [a for a in clips if a.confidence < .6]
    if unsure:
        a = unsure[-1]
        out.append((f"shot_shadow:{a.shot}", f"The model was only {round(a.confidence * 100)}% sure about your {a.shot} clip; a cleaner, slower shot helps.", {"clip_confidence_pct": round(a.confidence * 100)}))
    return out


def difficulty(c: Ctx, day: date) -> dict:
    """Harder after a strong week, easier after a weak one (last 7 days before this day)."""
    window = [d for d in c.drills if day - timedelta(days=7) <= d.day < day and d.code != "rest"]
    done = sum(d.done for d in window)
    rate = done / len(window) if window else None
    level, why = 2, "Normal level while we learn your routine."
    if window and len(window) >= 6:
        if rate >= .8:
            level, why = 3, f"Hard level: you finished {done} of {len(window)} drills in the last 7 days."
        elif rate < .4:
            level, why = 1, f"Easy level: {done} of {len(window)} drills were finished in the last 7 days, so we build back up."
        else:
            why = f"Normal level: you finished {done} of {len(window)} drills in the last 7 days."
    log = c.logs.get(day)
    if log and log.soreness == "mild":
        level, why = 1, "Easy level today because you reported mild soreness."
    return {"level": level, "label": DIFFICULTY[level], "why": why}


def make_plan(db: Session, c: Ctx, day: date) -> list[PlanDrill]:
    log = c.logs.get(day)
    if log and log.soreness == "stop":
        picks, diff = [("rest", "You reported soreness that needs rest, so today is a rest day. Training can wait.")], 1
    else:
        diff = difficulty(c, day)["level"]
        picks = [(code, why) for code, why, _ in weak_spots(c)][:3]
        start = day.toordinal() + c.user.id
        for i in range(len(GENERAL)):
            if len(picks) >= 3:
                break
            g = GENERAL[(start + i) % len(GENERAL)]
            if g not in {p[0] for p in picks}:
                picks.append((g, "A core batting habit to keep your movement sharp."))
    rows = []
    for code, why in picks:
        base, _, shot = code.partition(":")
        title = DRILLS[base][0].format(shot=shot)
        rows.append(PlanDrill(user_id=c.user.id, day=day, code=base, title=title, dose=dose(base, diff)[0],
                              reason=why, difficulty=diff))
    db.add_all(rows)
    db.commit()
    c.drills.extend(rows)
    return rows


def plan_for(db: Session, c: Ctx, day: date | None = None) -> list[PlanDrill]:
    day = day or c.day
    existing = [d for d in c.drills if d.day == day]
    return existing or make_plan(db, c, day)


def replan_today(db: Session, c: Ctx) -> None:
    """After a check-in, rebuild today's plan unless the player has already started it."""
    todays = [d for d in c.drills if d.day == c.day]
    if any(d.done for d in todays):
        return
    for d in todays:
        db.delete(d)
    db.commit()
    c.drills = [d for d in c.drills if d.day != c.day]
    make_plan(db, c, c.day)


def drill_out(d: PlanDrill) -> dict:
    _, how, unit, *_ = DRILLS[d.code]
    shot = d.title.split(": ", 1)[1] if d.code == "shot_shadow" else ""
    _, sets, amount = dose(d.code, d.difficulty)
    return {"id": d.id, "code": d.code, "title": d.title, "how": how.format(shot=shot), "dose": d.dose,
            "reason": d.reason, "difficulty": DIFFICULTY[d.difficulty], "done": d.done,
            "sets": sets, "amount": amount, "unit": unit}   # amount: reps, seconds or minutes per set


# ---------------------------------------------------------------- daily quiz

QUIZ = [
    ("q01", "In a pull shot, which foot usually moves first?",
     ["The back foot, back and across", "The front foot, down the pitch", "Neither foot moves", "Both feet jump together"], 0,
     "Against a short ball the back foot goes back and across, giving time and room to swing the bat across the line."),
    ("q02", "What is the main aim of the forward defence?",
     ["Hit the ball for four", "Stop the ball safely under the eyes", "Lift the ball over the field", "Leave the ball alone"], 1,
     "The forward defence smothers a good-length ball close to the body with soft hands so it drops safely."),
    ("q03", "Which length of ball suits a cover drive best?",
     ["Short and rising", "Full and outside off stump", "A bouncer at the head", "A ball down the leg side"], 1,
     "A full ball outside off stump can be met near its bounce and driven through the covers."),
    ("q04", "Where should your head be when you play a drive?",
     ["Leaning away to the leg side", "Over or just ahead of the front knee", "Behind the back foot", "Looking at the bowler's feet"], 1,
     "A head over the front knee keeps the weight forward and the bat swinging straight."),
    ("q05", "What does 'soft hands' mean in batting?",
     ["Wearing thin gloves", "Relaxing the grip at contact so the ball drops dead", "Gripping as tight as possible", "Using only the bottom hand"], 1,
     "A relaxed grip at impact takes the pace off the ball, which stops edges carrying to the fielders."),
    ("q06", "The sweep shot is mostly played against which kind of ball?",
     ["Fast short-pitched balls", "Full balls from spin bowlers", "Balls that bounce over the stumps", "Wide yorkers"], 1,
     "The sweep is usually played on one knee to a full ball from a spinner, hitting it square or fine on the leg side."),
    ("q07", "Which shot is played square on the off side to a short, wide ball?",
     ["Square cut", "Sweep", "Flick", "Straight drive"], 0,
     "The square cut punishes width: the batter rocks back and slaps the ball square through point."),
    ("q08", "What is a late cut?",
     ["A shot played before the ball bounces", "Steering the ball fine past the slips at the last moment", "A defensive block", "Hitting over mid-on"], 1,
     "The late cut uses the pace of the ball, guiding it fine on the off side with an angled bat."),
    ("q09", "Where should your weight be in the batting stance?",
     ["All on the heels", "Balanced, on the balls of the feet", "Fully on the back foot", "Fully on the front foot"], 1,
     "Weight on the balls of the feet lets you move forward or back quickly."),
    ("q10", "What is the backlift?",
     ["Picking the bat up as the bowler delivers", "Lifting the ball over the bowler", "Walking back to the crease", "The bat's handle grip"], 0,
     "A smooth backlift as the ball is bowled sets up a full, controlled swing."),
    ("q11", "When you leave a ball outside off stump, what should the bat do?",
     ["Push at the ball", "Lift high, out of the line of the ball", "Stay on the ground", "Swing across the line"], 1,
     "Lifting the bat away removes any chance of an edge."),
    ("q12", "A hook shot is played to a ball at about what height?",
     ["Ankle height", "Knee height", "Around shoulder or head height", "It never bounces"], 2,
     "The hook is played to a short ball rising to around shoulder or head height, hitting it to the leg side."),
    ("q13", "Which shot goes straight back past the bowler?",
     ["Square cut", "Straight drive", "Late cut", "Sweep"], 1,
     "The straight drive is played with a full face of the bat back down the ground."),
    ("q14", "What does a flick (or clip) off the pads do?",
     ["Turns a ball on the pads to the leg side with the wrists", "Leaves the ball", "Hits the ball over the slips", "Blocks it straight down"], 0,
     "The flick uses the wrists to turn a straight or leg-side ball into the on side."),
    ("q15", "Why does the app ask for side-on photos?",
     ["They load faster", "Knee, hip and elbow bends show clearly from the side", "Front-on photos are not allowed", "It looks better"], 1,
     "From the side, joint bends are seen in profile, so the angles measured from one 2D camera are more reliable."),
    ("q16", "What is the follow-through?",
     ["The bat continuing its swing after contact", "Running between the wickets", "The bowler's run-up", "Leaving the ball"], 0,
     "A full, balanced follow-through shows the bat travelled through the line of the ball."),
    ("q17", "What does 'getting to the pitch of the ball' mean?",
     ["Staying deep in the crease", "Stepping forward to meet the ball near its bounce", "Running down the pitch after the shot", "Watching the pitch report"], 1,
     "Meeting the ball near its bounce gives swing or spin less time to move it."),
    ("q18", "What is the aim of a lofted drive?",
     ["Hit the ball into the ground", "Hit over the infield with a full swing", "Block the ball", "Steer it to the keeper"], 1,
     "A lofted drive clears the inner ring of fielders, so the batter commits to a full, high swing."),
    ("q19", "Which part of the bat gives the cleanest contact?",
     ["The handle", "The toe", "The middle, or sweet spot", "The edge"], 2,
     "The sweet spot, a little below the middle of the blade, transfers the most energy to the ball."),
    ("q20", "What is a trigger movement?",
     ["A small step just before the ball is bowled to get moving", "A shout to the partner", "A bowling grip", "An appeal for LBW"], 0,
     "A small, early trigger movement gets the feet moving so the batter is balanced when the ball arrives."),
    ("q21", "In the forward defence, how should the bat face point?",
     ["Angled up to the sky", "Slightly down, towards the ground", "Sideways to the slips", "Flat towards the bowler's head"], 1,
     "Angling the face down keeps the ball on the ground."),
    ("q22", "How many legal balls are in a standard over?",
     ["Four", "Five", "Six", "Eight"], 2,
     "A standard over has six legal deliveries."),
]
QUIZ_BY_ID = {q[0]: q for q in QUIZ}


def quiz_today(c: Ctx) -> dict:
    ans = c.quiz.get(c.day)
    q = QUIZ_BY_ID[ans.question] if ans else QUIZ[(c.day.toordinal() + c.user.id * 5) % len(QUIZ)]
    out = {"id": q[0], "question": q[1], "options": q[2], "answered": None}
    if ans:
        out["answered"] = {"choice": ans.choice, "correct": ans.correct, "answer": q[3], "why": q[4]}
    return out


# ---------------------------------------------------------------- the coach's question about the latest upload

def reflection_question(c: Ctx) -> dict | None:
    recent = [a for a in c.analyses if local_day(a.created_at) >= c.day - timedelta(days=3)]
    for a in reversed(recent):
        if a.id in c.reflected:
            return None
        if a.mode == "video" and a.shot and a.confidence is not None:
            return {"analysis_id": a.id, "options": ["Yes", "No", "Not sure"],
                    "question": f"The model read your latest clip as a {a.shot} ({round(a.confidence * 100)}% sure). "
                                f"Was that the shot you played?"}
        if a.mode == "video" and not a.shot:
            knee = ((a.summary or {}).get("joint_ranges") or {})
            low = min((r["min"] for j, r in knee.items() if j.endswith("knee")), default=None)
            if low is not None:
                return {"analysis_id": a.id, "options": ["Felt good", "Felt stiff", "Off balance", "Not sure"],
                        "question": f"In your latest clip your front knee bent to {low}° at its deepest. How did the shot feel?"}
        if a.mode == "image" and (a.summary or {}).get("detected"):
            for joint, label in (("knee", "front knee"), ("elbow", "front elbow"), ("hip", "hip")):
                v = bent(a, joint)
                if v is not None:
                    return {"analysis_id": a.id, "options": ["Felt good", "Felt stiff", "Off balance", "Not sure"],
                            "question": f"Your {label} measured {v}° in your latest photo. How did it feel when you played it?"}
    return None


REFLECTION_REPLIES = {
    "Felt good": "Great. Keep that feeling in mind during today's drills.",
    "Felt stiff": "Thanks. A slower shadow round before you bat can help you loosen up. Take it easy.",
    "Off balance": "Noted. The finish-position balance drill is a good way to work on that.",
    "Not sure": "No problem. Try filming the same shot again and compare the numbers.",
    "Yes": "Good, the model agreed with you.",
    "No": "Thanks for telling me. The model can be wrong, especially on short or unclear clips. A side-on clip of one stroke helps.",
}


# ---------------------------------------------------------------- weekly report

def week_stats(c: Ctx, start: date) -> dict:
    end = start + timedelta(days=6)
    in_week = lambda d: start <= d <= end
    days = active_days(c)
    drills = [d for d in c.drills if in_week(d.day)]
    logs = [l for d, l in c.logs.items() if in_week(d)]
    week_photos = [a for a in photos(c) if in_week(local_day(a.created_at))]
    prev_photos = [a for a in photos(c) if in_week(local_day(a.created_at) + timedelta(days=7))]
    knee, prev_knee = mean(bent(a, "knee") for a in week_photos), mean(bent(a, "knee") for a in prev_photos)
    quiz = [q for d, q in c.quiz.items() if in_week(d)]
    done = sum(d.done for d in drills)
    joined = local_day(c.user.created_at) if c.user.created_at else start
    return {
        "week_start": start.isoformat(), "week_end": end.isoformat(),
        "days_so_far": max(0, min(7, (c.day - max(start, joined)).days + 1)),
        "week_in_progress": start <= c.day <= end,
        "joined_this_week": in_week(joined),
        "days_trained": sum(1 for d in days if in_week(d)),
        "drills_done": done, "drills_planned": len(drills),
        "completion_pct": round(done / len(drills) * 100) if drills else None,
        "balls_faced": sum(l.balls_faced or 0 for l in logs),
        "sore_days": sum(1 for l in logs if l.soreness in ("mild", "stop")),
        "analyses": sum(1 for a in c.analyses if in_week(local_day(a.created_at))),
        "knee_avg_deg": knee, "knee_avg_prev_week_deg": prev_knee,
        "knee_change_deg": round(knee - prev_knee, 1) if knee is not None and prev_knee is not None else None,
        "quiz_answered": len(quiz), "quiz_correct": sum(q.correct for q in quiz),
    }


def template_summary(s: dict) -> str:
    so_far = s.get("days_so_far", 7)
    in_progress = s.get("week_in_progress")
    first = (f"You trained on {s['days_trained']} of {so_far} day{'s' if so_far != 1 else ''} so far this week"
             if in_progress else f"You trained on {s['days_trained']} of 7 days this week")
    first += (f" and finished {s['drills_done']} of {s['drills_planned']} drills." if s["drills_planned"] else ".")
    lines = [first]
    if s["knee_change_deg"] is not None:
        ch = s["knee_change_deg"]
        lines.append(f"Your front-knee angle averaged {s['knee_avg_deg']}°, "
                     + (f"{abs(ch)}° {'deeper' if ch < 0 else 'straighter'} than last week." if ch else "the same as last week."))
    elif s["knee_avg_deg"] is not None:
        lines.append(f"Your front-knee angle averaged {s['knee_avg_deg']}° this week.")
    if s["balls_faced"]:
        lines.append(f"You logged {s['balls_faced']} balls faced.")
    if s["sore_days"]:
        lines.append(f"You reported soreness on {s['sore_days']} day{'s' if s['sore_days'] > 1 else ''}, so listen to your body.")
    rate = s["completion_pct"]
    if in_progress:
        left = max(0, 7 - so_far)
        lines.append(f"Keep it going: there {'is' if left == 1 else 'are'} {left} day{'' if left == 1 else 's'} left this week." if left
                     else "This is the last day of the week, so make it count.")
    else:
        lines.append("Next week's drills step up a level. Well done." if rate is not None and rate >= 80 else
                     "Next week's drills stay easier so you can build the habit." if rate is not None and rate < 40 else
                     "Keep the same rhythm next week.")
    return " ".join(lines)


WEEK_RULES = """You are a friendly cricket batting coach writing a short weekly summary for a player.
Use ONLY the numbers in the week JSON. Write 3 or 4 short sentences, warm and encouraging, in plain English.
Mention days trained and drills finished; mention the knee change only if knee_change_deg is not null
(negative means a deeper bend). Mention soreness only to suggest rest; never give medical advice.
completion_pct of 80 or more means next week gets harder; under 40 means easier. Never invent numbers.
If week_in_progress is true, the week is not over: talk about the days so far (days_so_far) and what is still possible,
never call it a bad or tough week. If joined_this_week is true, welcome the player and keep it encouraging."""


def weekly_summary(db: Session, c: Ctx, start: date, refresh: bool = False) -> WeeklyReport:
    report = db.scalar(select(WeeklyReport).where(WeeklyReport.user_id == c.user.id, WeeklyReport.week_start == start))
    stats = week_stats(c, start)
    if report and not refresh and report.stats == stats:
        return report  # nothing changed since the coach last wrote it
    text = template_summary(stats)
    if settings.llm_api_key:
        try:
            answer = coach._call([{"role": "system", "content": WEEK_RULES + "\n\nWeek JSON:\n" + json.dumps(stats)},
                                  {"role": "user", "content": "Write my weekly summary."}])
            if answer and coach.numbers_grounded(answer, stats):
                text = answer
        except Exception:
            pass  # keep the rule-based summary
    if report:
        report.text, report.stats, report.created_at = text, stats, datetime.now(timezone.utc)
    else:
        report = WeeklyReport(user_id=c.user.id, week_start=start, text=text, stats=stats)
        db.add(report)
    db.commit()
    return report


# ---------------------------------------------------------------- free chat with the coach

def player_facts(db: Session, c: Ctx) -> dict:
    st = status(c)
    plan = plan_for(db, c)
    log = c.logs.get(c.day)
    return {
        "name": c.user.name.split()[0] if c.user.name else "Player",
        "level": st["level"], "level_name": st["level_name"], "xp": st["xp"]["total"],
        "streak_days": st["streak"], "best_streak_days": st["best_streak"],
        "analyses": len(c.analyses), "photos": len(photos(c)),
        "today_checkin": {"balls_faced_yesterday": log.balls_faced, "soreness": log.soreness,
                          "feeling_1_to_5": log.feeling} if log else None,
        "today_plan": [{"drill": d.title, "dose": d.dose, "done": d.done, "why": d.reason,
                        "numbers": dose(d.code, d.difficulty)[1:]} for d in plan],
        "weak_spots": [extra for _, _, extra in weak_spots(c)],
        "this_week": week_stats(c, monday(c.day)),
    }


def chat_reply(db: Session, c: Ctx, text: str) -> str:
    """Coach on the Training page: the same AI Coach, talking about the plan, with the latest result to hand."""
    facts = {"player": player_facts(db, c)}
    if c.analyses:
        facts["latest_result"] = coach.facts_for(c.analyses[-1])
    history = db.scalars(select(TrainingChat).where(TrainingChat.user_id == c.user.id)
                         .order_by(TrainingChat.id.desc()).limit(6)).all()[::-1]
    return coach.converse(facts, [(m.role, m.text) for m in history], text, coach.TRAINING_RULES)


# ---------------------------------------------------------------- admin snapshot

def snapshot(user: User, db: Session) -> dict:
    c = load(user, db)
    days = active_days(c)
    cur, best = streaks(days, c.day)
    have = {"analyses": len(c.analyses), "best_streak": best, "full_photos": full_photos(c), "plan_weeks": plan_weeks(c)}
    lv = level_info(have)
    week = [d for d in c.drills if c.day - timedelta(days=6) <= d.day <= c.day]
    return {"level": lv["level"], "level_name": lv["name"], "streak": cur, "xp": xp(c, days)["total"],
            "plan_pct": round(sum(d.done for d in week) / len(week) * 100) if week else None}
