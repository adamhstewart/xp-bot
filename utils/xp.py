"""
XP calculation and level progression utilities
"""
from datetime import datetime
from zoneinfo import ZoneInfo

# XP/Level config
LEVEL_THRESHOLDS = [
    0, 300, 900, 2700, 6500, 14000, 23000, 34000, 48000, 64000,
    85000, 100000, 120000, 140000, 165000, 195000, 225000, 265000, 305000, 355000
]


def get_level_and_progress(xp):
    """Calculate level and progress from XP amount"""
    level = 1
    for i, threshold in enumerate(LEVEL_THRESHOLDS):
        if xp < threshold:
            level = i
            break
    else:
        level = 20

    if level == 20:
        return level, None, None

    current_threshold = LEVEL_THRESHOLDS[level - 1]
    next_threshold = LEVEL_THRESHOLDS[level]
    progress = xp - current_threshold
    required = next_threshold - current_threshold
    return level, progress, required


async def should_reset_xp(db, user_id: int):
    """Check if user needs daily XP reset"""
    now_utc = datetime.utcnow()
    tz = await db.get_user_timezone(user_id)
    try:
        user_time = now_utc.astimezone(ZoneInfo(tz))
    except Exception:
        user_time = now_utc
    today_local = user_time.date()

    last_reset = await db.get_last_xp_reset(user_id)
    return last_reset != today_local


async def perform_daily_reset(db, user_id: int):
    """Perform daily reset for a user"""
    await db.reset_daily_caps(user_id)

    now_utc = datetime.utcnow()
    tz = await db.get_user_timezone(user_id)
    try:
        user_time = now_utc.astimezone(ZoneInfo(tz))
    except Exception:
        user_time = now_utc

    await db.update_last_xp_reset(user_id, user_time.date())
