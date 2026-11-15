"""Constants for Community Apps."""

from datetime import timedelta

DOMAIN = "community_apps"
CATALOG_URL = "https://gluxur.github.io/ha-community-apps/catalog.json"
ENTRY_URL = "https://github.com/Gluxur/ha-community-apps/blob/main/catalog/repositories/{path}.yaml"
SCHEMA_VERSION = 1
UPDATE_INTERVAL = timedelta(hours=6)
PANEL_URL_PATH = "community-apps"
PANEL_COMPONENT = "community-apps-panel"
STATIC_PATH = "/community_apps_static"
