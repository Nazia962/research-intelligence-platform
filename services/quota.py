"""Plan limits and the daily AI counter (soft limits: there is no login)."""
from collections import namedtuple

from . import config, db

Limits = namedtuple("Limits", "compare_max workspaces papers_per_workspace watermark ai_per_day")


def limits_for(plan):
    if plan in ("pro", "open"):
        return Limits(config.PRO_COMPARE_MAX, config.UNLIMITED, config.UNLIMITED, False, None)
    return Limits(config.FREE_COMPARE_MAX, config.FREE_WORKSPACES, config.FREE_PAPERS_PER_WORKSPACE,
                  True, config.FREE_AI_PER_DAY)


def can_use_ai(owner, plan):
    """Return (allowed, reason). Cached results never go through this check."""
    if config.GLOBAL_AI_PER_DAY and db.usage_total() >= config.GLOBAL_AI_PER_DAY:
        return False, "The site has reached its daily AI capacity. Cached results still work; please try again tomorrow."
    lim = limits_for(plan)
    if lim.ai_per_day is not None and db.usage_count(owner) >= lim.ai_per_day:
        return False, f"You have used your {lim.ai_per_day} free AI generations for today."
    return True, ""


def record_ai_use(owner):
    db.usage_add(owner, 1)


def used_today(owner):
    return db.usage_count(owner)
