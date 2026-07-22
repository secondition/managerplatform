# Feature permissions gate whether an employee can use a module at all — when a
# user lacks one, the corresponding nav entry is hidden and the module's routes
# are blocked. Advanced permissions gate the admin backend tabs. Both are stored
# as UserPermission rows; owner bypasses only admin:* checks (see deps.require_permission).

# ---- feature permissions (module availability) ----
FEATURE_DAILY = "feature:daily"
FEATURE_TRAFFIC = "feature:traffic"
FEATURE_OKR = "feature:okr"
FEATURE_GROUP = "feature:group"

# ---- advanced permissions (admin backend) ----
ADMIN_EMPLOYEE = "admin:employee"
ADMIN_DEPARTMENT = "admin:department"
ADMIN_SETTINGS = "admin:settings"
ADMIN_AI = "admin:ai"

FEATURE_PERMISSIONS = [
    FEATURE_DAILY,
    FEATURE_TRAFFIC,
    FEATURE_OKR,
    FEATURE_GROUP,
]

ADVANCED_PERMISSIONS = [
    ADMIN_EMPLOYEE,
    ADMIN_DEPARTMENT,
    ADMIN_SETTINGS,
    ADMIN_AI,
]

# Everything assignable per user in the admin backend.
ASSIGNABLE_PERMISSIONS = FEATURE_PERMISSIONS + ADVANCED_PERMISSIONS

SYSTEM_PERMISSIONS = set(ASSIGNABLE_PERMISSIONS)

# New non-owner accounts get every feature module enabled by default; advanced
# (admin) permissions must be granted explicitly.
DEFAULT_FEATURE_PERMISSIONS = list(FEATURE_PERMISSIONS)
